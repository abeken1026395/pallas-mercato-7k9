# -*- coding: utf-8 -*-
# buildMotorUsage.py
# 人力で置かれた競走成績(Kファイル)群を自前集計し、各場のモーター機の
# 「モーター新替(推定)以降の走行数・勝・2連・3連」を docs/data/motorUsage.json に出力する。
#
# 収集はこのスクリプトの対象外（mbraceはActions/Code/本環境すべて403のため、
# Kファイルは人力(iPhone/PC)で取得し data/kfiles/ に置かれる前提）。本スクリプトは
# 「置かれたKファイル群を処理する部分」だけを担う。
#
# 入力：KFILES_DIR（既定 data/kfiles/）内の kYYMMDD.lzh（SHIFT_JIS・lhafile解凍）。
#       ローカル検証用に解凍済み .txt(SHIFT_JIS) も読める。
#       教師データ TEACHER（既定 docs/motor/motors_all.csv）の「モーター2連対率」。
# 出力：docs/data/motorUsage.json
#
# 集計窓（重要）:
#   モーターは年1回新替されるため、Kアーカイブ全期間を素で通算すると
#   「同じ機番を名乗った歴代モーターの合計」になる（若松49号機で 走2279・2連率36.4%）。
#   公式の「モーター2連対率」が新替からの累計であることを使い、場ごとに
#   「その日以降で数え直した2連率が公式値に最も近くなる開催日」を新替日として逆算する。
#   逆算できなかった場のモーターは出力しない（推測で埋めない）。
#
# 安全ゲート（重要）:
#   このスクリプトは scripts/dailyMotorUsage.ps1 から毎日06:00に無人で回され、
#   結果はそのまま自動コミット＆pushされる。人が数字を見て止める機会が無いため、
#   検算に通らなかった日は「出力を書かずに非0で落ちる」ことでその日の公開を止める。
#   ps1 の Invoke-Step が非0終了を例外にするので、落ちればコミットもpushもされない。
#   同じ実行の後段（backfillMotorPartsMotorNo.py によるモーターNo補填）も、
#   このスクリプトより後ろに並んでいるため一緒にスキップされる。
#   ゲートが働いた日は docs/data/motorUsage.json が前日のまま据え置かれる。
#   ＝古い数字は残るが、壊れた数字は出ない。
#     ゲート1（明細の内訳）  … 記号着順(F・S・L)の比率が 0.5%未満／5.0%超で NG
#     ゲート2（走行数の規模）… 推定成功が0場、または走行数の中央値が 100未満／250超で NG
#   ゲートを緩めて通すことはしない。通らない日は原因を直してから回すこと。
#
# ハルシネーション防止（絶対）:
#   Kファイルから読めた明細のみカウント。欠けた期間は補完・推測しない。
#   新替日は公式非公開のため推定値。推定に失敗した場は走行数を出さない。
import os
import re
import csv
import sys
import glob
import json
import datetime
import statistics
import tempfile
import subprocess

JST = datetime.timezone(datetime.timedelta(hours=9))

# LZH解凍: lhafile が使えればそれ、無ければWindows同梱bsdtar(libarchive)。
# lhafile は Python3.14 で C拡張のビルドが通らないため、bsdtar が実質の本命
# （scrapeKiryuPayouts.py も同じ理由で bsdtar を使っている）。
BSDTAR = os.environ.get(
    "BSDTAR",
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe"),
)

KFILES_DIR = os.environ.get("KFILES_DIR", os.path.join("data", "kfiles"))
TEACHER = os.environ.get("MOTORS_ALL_CSV", os.path.join("docs", "motor", "motors_all.csv"))
OUT = os.path.join("docs", "data", "motorUsage.json")

# 出力JSONの形式印。app.jsx はこの値が無いJSONの走行数を表示しない（旧形式の止血）。
SCHEMA = "venueWindow-1"

# 窓の逆算パラメータ。ここを緩めると「窓が効いていない場」を出力してしまう。
MIN_RUNS = 25      # 教師との照合に使うモーターの最低走行数（少走は率が振れて教師にならない）
MIN_MATCHED = 15   # 照合できたモーターがこれ未満の場は推定失敗
MAX_FIT_ERROR = 1.5  # 平均絶対誤差(pt)がこれを超えた場は推定失敗

# 安全ゲートの合格域。緩めない（通らない日は原因を直す）。
SYM_PCT_MIN, SYM_PCT_MAX = 0.5, 5.0    # ゲート1：記号着順(F・S・L)が数字着順に占める%
MEDIAN_MIN, MEDIAN_MAX = 100, 250      # ゲート2：推定成功場の走行数の中央値
GATE_EXIT = 2                          # ゲートNGの終了コード（ps1 はこれで止まる）

# 24場コード（scrape_motors.py の VENUES と同一）
VENUES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}
# 場名（全角/半角スペース除去）→ jcd。長い名前優先で照合（「津」と「唐津」の誤判定を防ぐ）。
NAME2JCD = sorted(((v, k) for k, v in VENUES.items()), key=lambda x: -len(x[0]))

SEISEKI = "［成績］"  # ［成績］
# 明細行（司令塔検証済み）：着順 艇 登番 氏名 モーターNo ボートNo 展示タイム…
# 着順は 01〜06 のほか F(フライング)・S0/S1/S2(失格)・L0/L1(出遅れ)・K0/K1(欠場) を取る。
# 公式の「モーター2連対率」の分母は出走回数で、フライングや失格も1走に数えられている
# （若松49号機・2025-11-26以降が 走135 になるのはこの数え方のときだけ）。
# 末尾の \d+\.\d+ は展示タイム。これが無い行＝出走していない（K0/K1 欠場等）は
# パターンに当たらず、そのまま走からも外れる。
DETAIL_RE = re.compile(r"\s*(\d{1,2}|[FSKL]\d?)\s+(\d)\s+(\d{4})\s+(.+?)\s+(\d{1,3})\s+(\d{1,3})\s+\d+\.\d+")
# 開催日「2026/ 7/ 8」形式
DATE_RE = re.compile(r"(\d{4})/\s*(\d{1,2})/\s*(\d{1,2})")


def mkey(v):
    """モーター番号の表記ゆれ（前ゼロ・空白）を吸収して比較キーにする。"""
    s = str(v or "").strip()
    return str(int(s)) if s.isdigit() else s


def unlzh(path):
    """.lzh を解凍し内側テキスト(K*.TXT)のバイト列を返す。lhafile→bsdtar の順に試す。"""
    try:
        import lhafile
    except ImportError:
        pass
    else:
        arc = lhafile.Lhafile(path)
        names = arc.namelist()
        return arc.read(names[0]) if names else b""

    with tempfile.TemporaryDirectory() as td:
        subprocess.run([BSDTAR, "-xf", path, "-C", td], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        txts = glob.glob(os.path.join(td, "*.TXT")) + glob.glob(os.path.join(td, "*.txt"))
        if not txts:
            return b""
        with open(txts[0], "rb") as f:
            return f.read()


def decode_kfile(path):
    """Kファイルを SHIFT_JIS テキストで返す。.lzh は解凍、.txt はそのまま。"""
    if path.lower().endswith(".lzh"):
        raw = unlzh(path)
    else:
        with open(path, "rb") as f:
            raw = f.read()
    return raw.decode("shift_jis", errors="replace")


def file_date(text, path):
    """ファイルの開催日(YYYYMMDD)。本文の日付行を優先、無ければ kYYMMDD のファイル名から。"""
    m = DATE_RE.search(text)
    if m:
        return "{:04d}{:02d}{:02d}".format(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    mm = re.search(r"[kK](\d{2})(\d{2})(\d{2})", os.path.basename(path))
    if mm:
        return "20{}{}{}".format(mm.group(1), mm.group(2), mm.group(3))
    return ""


def parse_text(text):
    """SHIFT_JIS本文から明細を返す：[(jcd, 着順, 艇, 登番, 氏名, モーターNo, ボートNo)]。
    着順は生の記号のまま返す（"03" のほか "F" "S1" 等）。着順の解釈は呼び出し側で行う。
    場ブロック見出し「○○［成績］」で現在の場を切り替える。"""
    out = []
    cur_jcd = None
    for ln in text.split("\n"):
        if SEISEKI in ln:
            head = ln.split(SEISEKI)[0].replace("　", "").replace(" ", "").strip()
            cur_jcd = None
            for name, jcd in NAME2JCD:  # 長い名前優先
                if head.endswith(name):
                    cur_jcd = jcd
                    break
            continue
        if cur_jcd is None:
            continue
        m = DETAIL_RE.match(ln)
        if not m:
            continue
        out.append((cur_jcd, m.group(1), int(m.group(2)),
                    m.group(3), m.group(4).strip(), m.group(5), m.group(6)))
    return out


# ===== 集計窓の逆算 =====================================================
# 教師：公式の「モーター2連対率」（=新替からの累計）。場コード・機番ごとに最新開催日のものを採る。
# 候補：その場でKファイルから読めた開催日すべて。
# 評価：候補日D以降で数え直した2連率と教師の絶対差の平均。最小のDをその場の新替日(推定)とする。

def load_teacher(path=TEACHER):
    """motors_all.csv → {jcd: {機番: 2連対率}}（場・機番ごとに最新開催日の行を採る）。"""
    if not os.path.exists(path):
        print("  [warn] 教師データが無い: {}".format(path))
        return {}
    latest = {}  # (jcd, mno) -> (開催日, rate)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            jcd = str(row.get("場コード") or "").strip().zfill(2)
            mno = mkey(row.get("モーター番号"))
            hd = str(row.get("開催日") or "").strip()
            try:
                rate = float(row.get("モーター2連対率"))
            except (TypeError, ValueError):
                continue
            if not jcd or not mno:
                continue
            cur = latest.get((jcd, mno))
            if cur is None or hd >= cur[0]:
                latest[(jcd, mno)] = (hd, rate)
    out = {}
    for (jcd, mno), (_hd, rate) in latest.items():
        out.setdefault(jcd, {})[mno] = rate
    return out


def solve_venue(by_day, teacher_v):
    """1場の集計窓を解く。

    by_day: {開催日: {機番: [走, 勝, 2連, 3連]}}
    teacher_v: {機番: 公式2連対率}
    戻り値: (新替日, 平均絶対誤差, 照合機数) or None（推定失敗）
    """
    if not by_day or not teacher_v:
        return None
    cum = {}   # 機番 -> [走, 勝, 2連, 3連]（[D, 最新日] の累計）
    best = None
    # 最新日から遡って累計すると、各Dの [D, 最新日] が1パスで出る。
    for D in sorted(by_day, reverse=True):
        for mno, c in by_day[D].items():
            a = cum.get(mno)
            if a is None:
                a = cum[mno] = [0, 0, 0, 0]
            a[0] += c[0]; a[1] += c[1]; a[2] += c[2]; a[3] += c[3]
        tot = 0.0
        n = 0
        for mno, rate in teacher_v.items():
            a = cum.get(mno)
            if a is None or a[0] < MIN_RUNS:  # 少走の機は教師にしない
                continue
            tot += abs(a[2] / a[0] * 100.0 - rate)
            n += 1
        if n < MIN_MATCHED:
            continue
        err = tot / n
        # 同点は新しい日を採る（遡るループなので先に見つかった方が新しい）。
        if best is None or err < best[1]:
            best = (D, err, n)
    if best is None or best[1] > MAX_FIT_ERROR:
        return None
    return best


def aggregate(records, teacher):
    """明細 [(開催日, jcd, 機番, 着順)] → (motors, venues)。

    場ごとに新替日を逆算し、推定に成功した場のモーターだけを [新替日, 最新日] で集計する。
    """
    by_venue = {}  # jcd -> {開催日: {機番: [走, 勝, 2連, 3連]}}
    for (hd, jcd, mno, chaku) in records:
        day = by_venue.setdefault(jcd, {}).setdefault(hd, {})
        a = day.get(mno)
        if a is None:
            a = day[mno] = [0, 0, 0, 0]
        a[0] += 1  # 出走は着順記号によらず1走（F・失格も公式の分母に入る）
        n = int(chaku) if str(chaku).isdigit() else 0
        if n == 1:
            a[1] += 1
        if 1 <= n <= 2:
            a[2] += 1
        if 1 <= n <= 3:
            a[3] += 1

    motors = {}
    venues = {}
    for jcd in sorted(by_venue):
        by_day = by_venue[jcd]
        got = solve_venue(by_day, teacher.get(jcd, {}))
        name = VENUES.get(jcd, jcd)
        if got is None:
            print("  [skip] {} {} … 新替日を推定できず（走行数を出さない）".format(jcd, name))
            continue
        start, err, matched = got
        venues[jcd] = {"coverageFrom": start, "fitError": round(err, 3), "matched": matched}
        for hd, day in by_day.items():
            if hd < start:
                continue
            for mno, c in day.items():
                key = "{}_{}".format(jcd, mno)
                d = motors.get(key)
                if d is None:
                    d = motors[key] = {"jcd": jcd, "モーターNo": mno,
                                       "走": 0, "勝": 0, "2連": 0, "3連": 0,
                                       "窓内初出日": hd, "最新日": hd}
                d["走"] += c[0]; d["勝"] += c[1]; d["2連"] += c[2]; d["3連"] += c[3]
                if hd < d["窓内初出日"]:
                    d["窓内初出日"] = hd
                if hd > d["最新日"]:
                    d["最新日"] = hd
        print("  [ok] {} {} … 新替日(推定) {} / 平均誤差 {:.2f}pt / 照合{}機".format(
            jcd, name, start, err, matched))

    for d in motors.values():
        w = d["走"]
        d["2連率"] = round(d["2連"] / w * 100, 1) if w else "-"
        d["3連率"] = round(d["3連"] / w * 100, 1) if w else "-"
    return motors, venues


def gate_detail_mix(records):
    """ゲート1：明細の内訳。着順が記号（F・S0/S1/S2・L0/L1）の行が数字着順の何%か。

    この割合は正規表現 DETAIL_RE の空振り・拾いすぎを見るための指標。
    Kアーカイブ1年分（kdata・2025-07-22〜2026-07-21）の実測で +1.21% だった。
    0%に近い＝記号着順を1行も拾えていない（数え方が変更前に戻っている）。
    5%超＝明細以外の行を拾っている疑い。どちらも走行数の分母が狂う。
    戻り値: (合格か, NGの説明文 or None)
    """
    total = len(records)
    if not total:
        return False, ("ゲート1 NG: 明細0行。Kファイルから1行も読めていない。出力は書いていない。"
                       "{} の中身と DETAIL_RE を確認すること".format(KFILES_DIR))
    sym = sum(1 for r in records if not str(r[3]).isdigit())
    num = total - sym
    if not num:
        return False, ("ゲート1 NG: 数字着順が0行（明細{:,}行すべてが記号着順）。出力は書いていない。"
                       "DETAIL_RE が明細以外の行を拾っている".format(total))
    pct = sym / num * 100.0
    ok = SYM_PCT_MIN <= pct <= SYM_PCT_MAX
    print("検算1: 明細{:,}行 = 数字着順{:,} + 記号着順(F・S・L){:,}（+{:.2f}%）… {}".format(
        total, num, sym, pct, "OK" if ok else "NG"))
    if ok:
        return True, None
    if pct < SYM_PCT_MIN:
        return False, ("ゲート1 NG: 記号着順 {:.2f}%（期待 +1.2%前後）。正規表現が空振りしている疑い。"
                       "出力は書いていない。DETAIL_RE を確認すること".format(pct))
    return False, ("ゲート1 NG: 記号着順 {:.2f}%（期待 +1.2%前後）。明細以外の行を拾っている疑い。"
                   "出力は書いていない。DETAIL_RE を確認すること".format(pct))


def gate_usage_scale(motors, venues):
    """ゲート2：走行数の規模。窓が効いていれば中央値は 100〜250 に入る。

    推定に成功した場が0場＝全場で新替日を逆算できていない。教師データとKアーカイブの
    期間が噛み合っていないときにこうなる。中央値が2000を超えるのは窓が効いておらず
    全期間を通算しているとき（この修正の前の状態）。
    戻り値: (合格か, NGの説明文 or None)
    """
    if not venues:
        return False, ("ゲート2 NG: 推定に成功した場が0場。全場で新替日を逆算できていない。"
                       "出力は書いていない。教師データ({}) の開催日とKアーカイブの期間が"
                       "噛み合っているか確認すること".format(TEACHER))
    runs = [d["走"] for d in motors.values()]
    if not runs:
        return False, ("ゲート2 NG: 推定成功{}場だが出力モーターが0機。出力は書いていない。"
                       "aggregate の窓の切り出しを確認すること".format(len(venues)))
    med = statistics.median(runs)
    ok = MEDIAN_MIN <= med <= MEDIAN_MAX
    print("検算2: 推定成功 {}場 / {}機 / 走行数中央値 {:.0f}（期待 {}〜{}）… {}".format(
        len(venues), len(runs), med, MEDIAN_MIN, MEDIAN_MAX, "OK" if ok else "NG"))
    if ok:
        return True, None
    if med > MEDIAN_MAX:
        return False, ("ゲート2 NG: 走行数中央値 {:.0f}（期待 {}〜{}）。窓が効いていない疑い"
                       "（2000超なら全期間を通算している）。出力は書いていない。"
                       "venues の coverageFrom と solve_venue を確認すること".format(
                           med, MEDIAN_MIN, MEDIAN_MAX))
    return False, ("ゲート2 NG: 走行数中央値 {:.0f}（期待 {}〜{}）。窓が短すぎる疑い"
                   "（Kアーカイブが新替日以降しか無いか、推定日が新しすぎる）。出力は書いていない。"
                   "venues の coverageFrom とKファイルの期間を確認すること".format(
                       med, MEDIAN_MIN, MEDIAN_MAX))


def main():
    files = sorted(glob.glob(os.path.join(KFILES_DIR, "*.lzh")) +
                   glob.glob(os.path.join(KFILES_DIR, "*.txt")))
    if not files:
        print("Kファイルが {} に無い。処理中止（既存を変更しない）。".format(KFILES_DIR))
        return

    teacher = load_teacher()
    if not teacher:
        print("教師データ（{} のモーター2連対率）が読めない。処理中止（既存を変更しない）。".format(TEACHER))
        return

    records = []
    dates = []
    for path in files:
        try:
            text = decode_kfile(path)
        except Exception as e:
            print("  [warn] 解凍/読込失敗 {}: {}".format(path, e))
            continue
        hd = file_date(text, path)
        if not hd:
            print("  [warn] 開催日不明のためスキップ: {}".format(path))
            continue
        dates.append(hd)
        details = parse_text(text)
        for (jcd, chaku, tei, toban, name, mno, bno) in details:
            records.append((hd, jcd, mkey(mno), chaku))
        print("  [ok] {} ({}) … 明細{}件".format(os.path.basename(path), hd, len(details)))

    # 集計 → 検算 → 書き出し の順。ゲートに1つでも落ちたら書かずに非0で終わる
    # （ps1 の Invoke-Step がここで例外を投げ、コミットもpushも後段のbackfillも走らない）。
    ok, ng = gate_detail_mix(records)
    if not ok:
        print(ng)
        sys.exit(GATE_EXIT)

    motors, venues = aggregate(records, teacher)

    ok, ng = gate_usage_scale(motors, venues)
    if not ok:
        print(ng)
        sys.exit(GATE_EXIT)

    out = {
        "updated": datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "schema": SCHEMA,
        "source": "mbrace競走成績(K)由来・自前集計",
        "note": ("走行数はモーター新替(推定)以降の実測カウント。新替日は公式非公開のため、"
                 "公式のモーター2連対率（新替からの累計）と突き合わせて場ごとに逆算した推定値。"
                 "推定できなかった場は出力しない。欠損期間は補完しない。"),
        "coverageFrom": min(dates) if dates else "",
        "coverageTo": max(dates) if dates else "",
        "venues": venues,
        "motors": motors,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("ゲート通過。{} を書き出した（venues {}場）".format(OUT.replace(os.sep, "/"), len(venues)))
    print("  {}ファイル / 明細{}件 / {}機 / Kアーカイブ {}〜{}".format(
        len(files), len(records), len(motors), out["coverageFrom"], out["coverageTo"]))


if __name__ == "__main__":
    main()
