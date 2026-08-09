# -*- coding: utf-8 -*-
# buildM8Features.py
# M8（①＝1号艇が着外＝4着以下 になる確率のモデル）の特徴量テーブルを作る。
# 影運用（記録だけして読者の画面は変えない）の素材づくり専用。
#
# 取得元と保存先:
#   ・番組表 https://raw.githubusercontent.com/BoatraceOpenAPI/programs/HEAD/docs/v2/YYYY/YYYYMMDD.json
#   ・直前情報 https://raw.githubusercontent.com/BoatraceOpenAPI/previews/HEAD/docs/v2/YYYY/YYYYMMDD.json
#     いずれも 20250715 以降が現存する（それ以前は404）。
#     boatraceopenapi/api v1（buildPreview.py / buildResults.py の取得元）は2026-01-01以降しか無く、
#     2025年分の番組表・直前情報は v2 でしか取れない。だから素材は v2 を使う。
#   ・生キーのまま pv2/programs/YYYYMMDD.json.gz / pv2/previews/YYYYMMDD.json.gz に保存する。
#     改名も単位変換もしない（buildPreview.py の保存方針に合わせる）。gzip なのは
#     生JSONだと1日827KB・391日で311MBになりリポジトリが持たないため（gzipなら1日56KB・391日22MB）。
#   ・結果（着順）は既にリポジトリにある results/YYYYMMDD.json を使う。v2 results と全期間で
#     突合したところ 着/登番/コース は完全一致で、さらに v2 に無い198レースを持っている（＝上位互換）。
#
# 増分更新について:
#   ・pv2/ の取得は増分（既にあるファイルは触らない・再取得しない）。
#   ・特徴量テーブルそのものは毎回 全期間を作り直す。履歴系の特徴量が
#     「前日までの累積」を時系列に走査して作る性質上、途中から継ぎ足せないため。
#     実測で391日ぶん約20秒なので分割しない。
#
# リークの掟（Phase3.5/3.6 の検証で確定した内容。緩めないこと）:
#   ・履歴系はすべて「前日まで」で打ち切る。当日の結果は日が変わってから反映する。
#   ・docs/data/motorUsage.json は現時点までの累積なので使わない（過去に当てると未来が混ざる）。
#   ・docs/data/racerStats.json の c1（fan2604 の期首固定値）は使わない。
#     2025-11〜2026-04 の結果を含むため、その期間のバックテストが上振れすることを実測で確認済み
#     （2026-01〜04 で AUC +0.013〜+0.021、2026-05〜08 では ±0.003 とぴたり一致した）。
#     コース別1着率のプライアは「前日までのコース別 全体1着率」を使う。
#   ・展示タイム・展示STは締切前に確定する値なので当日ぶんを使ってよい。
#
# 使い方:
#   python scripts/buildM8Features.py            … 既定期間ぶんを取得して表を作る
#   HD=20260809 python scripts/buildM8Features.py … 対象日を指定（既定はJST当日）
#   M8_WORK=/path/features.csv.gz                … 出力先（既定は一時ディレクトリ。リポジトリには置かない）
import io
import os
import csv
import gzip
import json
import time
import tempfile
import datetime
import collections
import urllib.request

BASE = "https://raw.githubusercontent.com/BoatraceOpenAPI/{0}/HEAD/docs/v2/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) boatrace-data-collector"}

PV2_DIR = os.environ.get("M8_PV2", "pv2")
RESULTS_DIR = os.environ.get("M8_RESULTS", "results")
HIST_FIRST = os.environ.get("M8_FIRST", "20250715")     # v2配信の最古日
TRAIN_FIRST = os.environ.get("M8_TRAIN_FIRST", "20250901")  # 学習に使う最初の日（それ以前は履歴の助走）

# 着順コードの意味（kdata/entriesFull.csv の chaku と全期間突合して確定した）
#   1-6=着順 / 7=妨害失格 / 8-13=転覆・落水など / 14=F / 15=L / 16=K（欠場）
PLACE_ABSENT = 16

# Phase3.6 で確定した M8 の特徴量22列。順番も含めてここが正本。
M8_FEATURES = [
    "tenjiDev1", "motor1", "f1_recent5", "cWin1_bl0", "f4_cWin4_bl0",
    "f2_cWin2_bl0", "f3_cWin3_bl0", "sectAvgPlace1", "grade", "raceNo", "class1",
    "pubNat1_1", "pubNat2_1", "pubLoc1_1", "pubAvgST_1", "pubF_1",
    "pubNat1_2", "pubNat1_3", "pubNat1_4", "motor1_pub", "sub_cat", "sub_te",
]
# LR側でダミー化する列と、その水準（先頭水準は落とす）
M8_CATEGORICAL = {"grade": [2, 3, 4, 5], "class1": [1, 2, 3, 4], "sub_cat": list(range(7))}

OUT_COLS = ["hd", "jcd", "rno", "y"] + M8_FEATURES

# race_subtitle の6分類（上から先勝ち）。Phase3.6 の写像表そのまま。
SUBTITLE_RULES = [
    ("準優", ("準優",)),
    ("優勝", ("優勝",)),
    ("特賞・選抜", ("特賞", "特選", "選抜", "ドリーム", "特別")),
    ("予選", ("予選",)),
    ("一般", ("一般",)),
]
SUBTITLE_ORDER = ["予選", "特賞・選抜", "準優", "優勝", "企画", "一般", "その他"]
SUB_TE_MIN_N = 30


def jst_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()


def daterange(a, b):
    d = datetime.datetime.strptime(a, "%Y%m%d").date()
    e = datetime.datetime.strptime(b, "%Y%m%d").date()
    while d <= e:
        yield d.strftime("%Y%m%d")
        d += datetime.timedelta(days=1)


def pv2_path(kind, hd):
    return os.path.join(PV2_DIR, kind, "%s.json.gz" % hd)


def fetch_pv2(kind, hd, retries=4):
    """未取得なら pv2/ に生キーのまま gzip 保存する。取れたら True。404 は False。
    既にあるファイルは絶対に取り直さない（write-once）。"""
    p = pv2_path(kind, hd)
    if os.path.exists(p):
        return True
    url = "{0}{1}/{2}.json".format(BASE.format(kind), hd[:4], hd)
    for i in range(retries):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
        except Exception as e:
            if "404" in str(e):
                return False
            time.sleep(2 ** i)
            continue
        if not raw or len(raw) < 50:
            return False
        try:
            json.loads(raw.decode("utf-8"))
        except Exception:
            return False
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with gzip.open(p, "wb") as f:
            f.write(raw)
        return True
    return False


def ensure_pv2(days, verbose=True):
    """指定日ぶんの pv2/ を揃える（増分）。取得した日数と欠けた日を返す。"""
    got, miss = 0, []
    for hd in days:
        ok = True
        for kind in ("programs", "previews"):
            if os.path.exists(pv2_path(kind, hd)):
                continue
            if fetch_pv2(kind, hd):
                got += 1
            else:
                ok = False
        if not ok:
            miss.append(hd)
    if verbose:
        print("pv2: 新規取得 %d ファイル / 揃わなかった日 %d（%s）"
              % (got, len(miss), ",".join(miss[-5:]) if miss else "-"))
    return got, miss


def load_pv2(kind, hd):
    p = pv2_path(kind, hd)
    if not os.path.exists(p):
        return None
    try:
        with gzip.open(p, "rb") as f:
            return json.load(f)
    except Exception:
        return None


def boats(r):
    """boats は配信の途中で 配列 → 艇番キーの辞書 に形が変わっている
    （実測: list 11,762レース / dict 47,698レース）。配列に正規化する。"""
    b = (r or {}).get("boats")
    if isinstance(b, list):
        return b
    if isinstance(b, dict):
        return [v for _, v in sorted(b.items(), key=lambda kv: int(kv[0]))]
    return []


def exhibition_time(boat):
    """展示タイムを返す。取れていないものは None。

    ★配信の仕様に罠がある。まだ展示が終わっていないレースや、
      走らなかった艇の展示タイムは null ではなく **0** で入ってくる
      （実測: pv2/previews 全期間 357,770枠のうち 0 が 5,388枠＝1.5%。
        うち当日未実施ぶんが 732枠、残り 4,656枠は過去日の欠測）。
      0 をそのまま数字として使うと、他艇平均が引きずられて偏差が
      ±1秒を超える異常値になる（Phase3.6 のデータでは 529レースが該当）。
      正の値だけを有効とみなす。"""
    v = (boat or {}).get("racer_exhibition_time")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def load_results(hd):
    """results/YYYYMMDD.json を (jcd,rno) -> {枠: (登番,着,コース)} に読み替える。"""
    p = os.path.join(RESULTS_DIR, "%s.json" % hd)
    if not os.path.exists(p):
        return {}
    try:
        with io.open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return {}
    out = {}
    for r in d.get("結果") or []:
        try:
            jcd = int(r["場コード"])
            rno = int(str(r["レース"]).replace("R", ""))
        except Exception:
            continue
        m = {}
        for b in r.get("艇") or []:
            try:
                m[int(b["枠"])] = (b.get("登番"), b.get("着"), b.get("コース"))
            except Exception:
                continue
        out[(jcd, rno)] = m
    return out


def subtitle_category(s):
    s = (s or "").strip()
    if not s:
        return "その他"
    for name, pats in SUBTITLE_RULES:
        for pat in pats:
            if pat in s:
                return name
    # 標準の番組名に当たらない＝場固有の企画レース名
    return "企画"


def build(last_hd, first_hd=None, allow_no_result=True):
    """first_hd〜last_hd の特徴量行を作って返す。
    allow_no_result=True のとき、結果がまだ無い日（＝当日）の行も y を空にして出す。"""
    first_hd = first_hd or HIST_FIRST
    days = list(daterange(first_hd, last_hd))

    # ---- 1. 素材を (hd,jcd,rno) にまとめる ----
    prog, prev, resu = {}, {}, {}
    titles = collections.defaultdict(dict)     # jcd -> hd -> race_title
    for hd in days:
        pg = load_pv2("programs", hd)
        if pg:
            for r in pg.get("programs") or []:
                jcd, rno = int(r["race_stadium_number"]), int(r["race_number"])
                prog[(hd, jcd, rno)] = r
                titles[jcd][hd] = r.get("race_title") or ""
        pv = load_pv2("previews", hd)
        if pv:
            for r in pv.get("previews") or []:
                prev[(hd, int(r["race_stadium_number"]), int(r["race_number"]))] = r
        for k, v in load_results(hd).items():
            resu[(hd, k[0], k[1])] = v

    # ---- 2. 節（開催）の割り当て：同一場で日付が連続し race_title が同じ区間を1節とする ----
    sect_of = {}
    for jcd, m in titles.items():
        prev_d, prev_t, sid = None, None, 0
        for hd in sorted(m):
            d = datetime.datetime.strptime(hd, "%Y%m%d").date()
            t = m[hd]
            if prev_d is None or (d - prev_d).days > 1 or t != prev_t:
                sid += 1
            sect_of[(hd, jcd)] = "%02d-%05d" % (jcd, sid)
            prev_d, prev_t = d, t

    # ---- 3. 時系列に走査して履歴を積む（前日まで打ち切り） ----
    rc_n, rc_w = collections.defaultdict(int), collections.defaultdict(int)     # 選手×コース 出走/1着
    cc_n, cc_w = collections.defaultdict(int), collections.defaultdict(int)     # コース別 全体 出走/1着
    recent = collections.defaultdict(collections.deque)                          # 選手 直近の着
    mt_n, mt_t2 = collections.defaultdict(int), collections.defaultdict(int)     # モーター 通算
    rs_sum, rs_cnt = collections.defaultdict(float), collections.defaultdict(int)  # 選手×節 の着
    pend = []

    def flush():
        for (toban, course, place, jcd, motorno, sid) in pend:
            if course:
                rc_n[(toban, course)] += 1
                cc_n[course] += 1
                if place == 1:
                    rc_w[(toban, course)] += 1
                    cc_w[course] += 1
            dq = recent[toban]
            dq.appendleft(min(place, 6))
            while len(dq) > 10:
                dq.pop()
            if sid:
                rs_sum[(toban, sid)] += min(place, 6)
                rs_cnt[(toban, sid)] += 1
            if motorno:
                mt_n[(jcd, motorno)] += 1
                if place <= 2:
                    mt_t2[(jcd, motorno)] += 1
        pend.clear()

    def blend0(toban, course):
        """n走の実測と「前日までのコース別 全体1着率」を n/(n+10):10/(n+10) で混ぜる。
        未来情報を一切含まないプライア。"""
        if not toban or cc_n[course] < 200:
            return None
        n = rc_n[(toban, course)]
        obs = (rc_w[(toban, course)] / float(n)) if n else 0.0
        pv = cc_w[course] / float(cc_n[course])
        return (n * obs + 10.0 * pv) / (n + 10.0)

    # subtitle のターゲットエンコード用（前日まで）
    te_n, te_y = collections.defaultdict(int), collections.defaultdict(int)
    te_all_n = te_all_y = 0
    te_pend = []

    rows = []
    for hd in days:
        # 日が変わったので、前日ぶんの更新をここで反映する
        flush()
        for s, yy in te_pend:
            te_n[s] += 1
            te_y[s] += yy
            te_all_n += 1
            te_all_y += yy
        te_pend = []

        keys = sorted([k for k in prog if k[0] == hd], key=lambda k: (k[1], k[2]))
        for k in keys:
            _, jcd, rno = k
            pg = prog[k]
            pv = prev.get(k)
            rs = resu.get(k)
            sid = sect_of.get((hd, jcd))
            pgb = {}
            for b in boats(pg):
                try:
                    pgb[int(b["racer_boat_number"])] = b
                except Exception:
                    continue

            # --- 当日ぶんの履歴更新を先に積む（反映は翌日）。
            #     行を作らないレース（①欠場など）の結果も履歴には入れる。 ---
            if rs:
                for w, (tob, pl, co) in rs.items():
                    if tob is None or pl is None or int(pl) >= PLACE_ABSENT:
                        continue
                    mo = (pgb.get(w) or {}).get("racer_assigned_motor_number")
                    pend.append((int(tob), int(co) if co else None, int(pl), jcd,
                                 int(mo) if mo else None, sid))

            if 1 not in pgb:
                continue

            # --- 目的変数 ---
            y = None
            if rs:
                pl = (rs.get(1) or (None, None, None))[1]
                if pl is not None and int(pl) < PLACE_ABSENT:
                    y = 0 if int(pl) <= 3 else 1
            if y is None and (rs or hd != last_hd or not allow_no_result):
                # 結果があるのに①が欠場・不明／過去日で結果がまだ無い日 → 行を作らない。
                # 行を作るのは「結果あり」か「対象日（＝これから推論する日）」だけ。
                continue

            pvb = {}
            if pv:
                for b in boats(pv):
                    try:
                        pvb[int(b["racer_boat_number"])] = b
                    except Exception:
                        continue

            row = {"hd": hd, "jcd": jcd, "rno": rno, "y": y}

            # 展示タイム偏差（同一レース内の他艇平均との差＝leave-one-out）
            ex = dict((w, exhibition_time(pvb.get(w))) for w in range(1, 7))
            oth = [ex[w] for w in range(2, 7) if ex.get(w) is not None]
            row["tenjiDev1"] = (ex[1] - sum(oth) / float(len(oth))) if (ex.get(1) is not None and len(oth) >= 3) else None

            # モーター
            mo1 = pgb[1].get("racer_assigned_motor_number")
            mo1 = int(mo1) if mo1 else None
            n = mt_n[(jcd, mo1)] if mo1 else 0
            row["motor1"] = (mt_t2[(jcd, mo1)] / float(n)) if (mo1 and n >= 10) else None
            mp = pgb[1].get("racer_assigned_motor_top_2_percent")
            row["motor1_pub"] = (float(mp) / 100.0) if mp is not None else None

            # 選手（登番）
            tb = dict((w, (pgb.get(w) or {}).get("racer_number")) for w in range(1, 7))
            t1 = int(tb[1]) if tb.get(1) else None
            row["cWin1_bl0"] = blend0(t1, 1)
            row["f2_cWin2_bl0"] = blend0(int(tb[2]) if tb.get(2) else None, 2)
            row["f3_cWin3_bl0"] = blend0(int(tb[3]) if tb.get(3) else None, 3)
            row["f4_cWin4_bl0"] = blend0(int(tb[4]) if tb.get(4) else None, 4)

            dq = list(recent[t1])[:5] if t1 else []
            row["f1_recent5"] = (sum(dq) / float(len(dq))) if len(dq) >= 3 else None
            c = rs_cnt[(t1, sid)] if t1 else 0
            row["sectAvgPlace1"] = (rs_sum[(t1, sid)] / float(c)) if c >= 1 else None

            # 番組表の公表値（締切前に確定し期の途中で動かない＝リーク無し）
            for w in (1, 2, 3, 4):
                row["pubNat1_%d" % w] = (pgb.get(w) or {}).get("racer_national_top_1_percent")
            b1 = pgb[1]
            row["pubNat2_1"] = b1.get("racer_national_top_2_percent")
            row["pubLoc1_1"] = b1.get("racer_local_top_1_percent")
            row["pubAvgST_1"] = b1.get("racer_average_start_timing")
            row["pubF_1"] = b1.get("racer_flying_count")

            # 番組情報
            row["grade"] = pg.get("race_grade_number")
            row["raceNo"] = rno
            row["class1"] = b1.get("racer_class_number")
            sub = pg.get("race_subtitle") or ""
            row["sub_cat"] = SUBTITLE_ORDER.index(subtitle_category(sub))
            ns = te_n.get(sub, 0)
            if te_all_n >= SUB_TE_MIN_N:
                row["sub_te"] = (te_y[sub] / float(ns)) if ns >= SUB_TE_MIN_N else (te_all_y / float(te_all_n))
            else:
                row["sub_te"] = None

            rows.append(row)
            if y is not None:
                te_pend.append((sub, y))
    return rows


def write_csv(rows, path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS)
        w.writeheader()
        for r in rows:
            w.writerow(dict((c, r.get(c)) for c in OUT_COLS))


def default_work_path():
    return os.environ.get("M8_WORK", os.path.join(tempfile.gettempdir(), "m8features.csv.gz"))


def main():
    hd = (os.environ.get("HD") or "").strip() or jst_today().strftime("%Y%m%d")
    t0 = time.time()
    ensure_pv2(list(daterange(HIST_FIRST, hd)))
    t1 = time.time()
    rows = build(hd)
    t2 = time.time()
    out = default_work_path()
    write_csv(rows, out)
    lab = sum(1 for r in rows if r["y"] is not None)
    print("対象日 %s / 行数 %d（うち結果あり %d・当日 %d）"
          % (hd, len(rows), lab, sum(1 for r in rows if r["hd"] == hd)))
    print("所要: pv2取得 %.1fs / 特徴量構築 %.1fs / 書き出し %.1fs → %s"
          % (t1 - t0, t2 - t1, time.time() - t2, out))


if __name__ == "__main__":
    main()
