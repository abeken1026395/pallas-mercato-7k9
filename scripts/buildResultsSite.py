# -*- coding: utf-8 -*-
# buildResultsSite.py
# results/YYYYMMDD.json(リポジトリ直下・GitHub Pages非配信)を、
# 結果表ページ docs/results/ から読める公開用データに変換する。
#   出力: docs/results/data/YYYYMMDD.json  … 1日分(コンパクト)
#         docs/results/data/index.json     … 日付一覧(新しい順)+開催場数
#
# 元データは buildResults.py が BoatraceOpenAPI から生成したもので、
# 着順・決まり手・全式別払戻・艇別を含む。ここでは表示に必要な項目を
# そのまま公開領域(docs/)へコピーするだけ(判定・予想は元から無い)。
#
# 使い方: python scripts/buildResultsSite.py
#   ・results/*.json のうち新しい方から SITE_DAYS 日分を docs/results/data/ に再生成し、
#     期間外の古い出力は取り除く。
import io
import os
import re
import json
import glob

SRC_DIR = "results"
PREVIEW_DIR = "preview"
OUT_DIR = os.path.join("docs", "results", "data")

# docs/ の肥大化を防ぐための表示用の保持日数。元データは results/ に全期間ある。
SITE_DAYS = 30

# 場コード → 場名(build_arare.py と同一)
STADIUM = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
    "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
    "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀",
    "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}


def race_no(r):
    """'11R' → 11。並べ替え用。"""
    m = re.match(r"(\d+)", str(r.get("レース", "")))
    return int(m.group(1)) if m else 0


def load_tenji_dev(hd):
    """preview/YYYYMMDD.json から (場コード, レース) → {枠: 展示偏差} を作る。

    展示タイムの生の秒数は水面・気象で基準が動くため公開しない。
    同じレースの6艇平均との差（偏差）だけを出す。条件は定義上キャンセルされる。
    6艇そろわない・展示タイムが欠けるレースは載せない（分母の欠けた値を出さない）。
    preview/ が無い日は空を返し、展示偏差が付かないだけで処理は続く。
    """
    dev = {}
    path = os.path.join(PREVIEW_DIR, "%s.json" % hd)
    if not os.path.exists(path):
        return dev
    try:
        pv = json.load(io.open(path, encoding="utf-8"))
    except Exception as e:
        print("preview skip", hd, e)
        return dev
    for r in pv.get("直前情報", []) or []:
        ts = {}
        for x in r.get("racers", []) or []:
            w = x.get("entry_number")
            t = x.get("exhibition_time")
            if w and t:
                ts[int(w)] = float(t)
        if len(ts) != 6:
            continue
        avg = sum(ts.values()) / 6.0
        key = (str(r.get("場コード", "")).zfill(2), str(r.get("レース", "")))
        dev[key] = dict((w, round(t - avg, 3)) for w, t in ts.items())
    return dev


def build_day(path):
    """1日分の results JSON を公開用の辞書に整形して返す。"""
    d = json.load(io.open(path, encoding="utf-8"))
    hd = d.get("開催日") or os.path.basename(path)[:8]
    races = d.get("結果", []) or []
    # 当日の展示タイム偏差を各艇に付ける。見どころの深層で「その日の先行レース」を
    # 生データとして出すために使う（買い目・予想は出さない。数字を置くだけ）。
    dev = load_tenji_dev(hd)
    if dev:
        for r in races:
            key = (str(r.get("場コード", "")).zfill(2), str(r.get("レース", "")))
            dv = dev.get(key)
            if not dv:
                continue
            for b in r.get("艇", []) or []:
                v = dv.get(b.get("枠"))
                if v is not None:
                    b["展示偏差"] = v
    # 場コード → レース配列
    venues = {}
    for r in races:
        jcd = str(r.get("場コード", "")).zfill(2)
        venues.setdefault(jcd, []).append(r)
    stadiums = []
    for jcd in sorted(venues.keys()):
        rs = sorted(venues[jcd], key=race_no)
        stadiums.append({
            "場コード": jcd,
            "場名": STADIUM.get(jcd, jcd),
            "レース": rs,
        })
    return {
        "開催日": hd,
        "取得時刻": d.get("取得時刻"),
        "レース数": len(races),
        "場数": len(stadiums),
        "場": stadiums,
    }


def prune(keep):
    """保持期間外(と空になった日)の公開データを docs/results/data から取り除く。
    これをやらないと、次回以降も古い分が残り続けて docs/ が肥大化する。"""
    for path in sorted(glob.glob(os.path.join(OUT_DIR, "*.json"))):
        name = os.path.basename(path)
        if not re.match(r"^\d{8}\.json$", name):
            continue  # index.json などは対象外
        if name[:8] in keep:
            continue
        os.remove(path)
        print("prune", name[:8])


def write_stamp(index):
    """更新の印 now.json（2026-11-12）。直近2日の「取得時刻」とレース数だけを書く（約100バイト）。
    画面（assets/kotaeawase.js）はこれを15秒ごとに読み、変わった日だけ結果データ（1日約0.2MB）を読み直す。
    中身が同じなら書かない（コミットを増やさない）。"""
    d = {}
    for x in index[:2]:
        hd = x["開催日"]
        try:
            with io.open(os.path.join(OUT_DIR, "%s.json" % hd), encoding="utf-8") as f:
                t = json.load(f).get("取得時刻") or ""
        except (OSError, ValueError):
            t = ""
        d[hd] = {"t": t, "n": x["レース数"]}
    body = json.dumps({"d": d}, ensure_ascii=False, separators=(",", ":"))
    path = os.path.join(OUT_DIR, "now.json")
    try:
        with io.open(path, encoding="utf-8") as f:
            if f.read() == body:
                return
    except OSError:
        pass
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(body)
    print("wrote", path, body)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # 元データ results/ は全期間そのまま読み、公開するのは新しい方から SITE_DAYS 日分だけ。
    paths = sorted(
        p for p in glob.glob(os.path.join(SRC_DIR, "*.json"))
        if re.match(r"^\d{8}$", os.path.basename(p)[:8])
    )
    all_paths = paths
    paths = paths[-SITE_DAYS:]
    index = []
    for path in paths:
        hd = os.path.basename(path)[:8]
        try:
            day = build_day(path)
        except Exception as e:
            print("skip", hd, e)
            continue
        # 確定レースが1つも無い日(早朝の未確定など)は公開しない。
        # 当日分はレース確定ごとに随時再生成され、順次公開に載る。
        # 既に空データを公開済みの場合は下の prune() が取り除く。
        if day["レース数"] <= 0:
            print("skip empty", hd)
            continue
        outpath = os.path.join(OUT_DIR, "%s.json" % hd)
        with io.open(outpath, "w", encoding="utf-8") as f:
            json.dump(day, f, ensure_ascii=False, separators=(",", ":"))
        index.append({"開催日": hd, "場数": day["場数"], "レース数": day["レース数"]})
    index.sort(key=lambda x: x["開催日"], reverse=True)
    # index.json は今回出力した分だけを載せる(削除した日が一覧に残らないようにする)。
    prune(set(x["開催日"] for x in index))
    with io.open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"件数": len(index), "日付": index}, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote", len(index), "days to", OUT_DIR)
    write_stamp(index)
    build_hit(all_paths)


# ---- 買い目で絞り込む（結果ページ）用：全期間の払戻だけを月ごとにまとめる ----
#   出力: docs/results/data/hit/YYYYMM.json … その月の全レースの払戻（7券種）
#         docs/results/data/hit/index.json  … 月の一覧（新しい順）と全期間の範囲
#   1レース＝[日(2桁), 場コード(数), レース番号(数), 券種ごとの [[組, 配当], ...] × 7]
#   組は艇番の数字だけ。単式（単勝・2連単・3連単）は着順のまま、複式は小さい順に並べる。
#   作り直すのは「直近 SITE_DAYS 日が入る月」と「まだファイルが無い月」だけ（毎回486日を読まない）。
#   その月に読めない日が1日でもあれば、その月は書き換えない（前回のファイルを残す）。
#   日時は入れない（中身が変わらない限りファイルが変わらないようにする）。
#   いちばん新しい日（取り込み中の日）は入れない。その日はレースが確定するたびに変わるので、
#   月のファイルに入れると1日150回ほど書き換わってリポジトリが膨らむ。ページは、その日を
#   1日分の結果（docs/results/data/YYYYMMDD.json）から足す。index.json の「当日」がその日。
HIT_DIR = os.path.join(OUT_DIR, "hit")
HIT_TYPES = ["単勝", "複勝", "2連単", "2連複", "拡連複", "3連複", "3連単"]
HIT_UNORDERED = {"2連複", "拡連複", "3連複"}


def hit_combo(t, s):
    ds = re.findall(r"[1-6]", str(s))
    if t in HIT_UNORDERED:
        ds = sorted(ds)
    return "".join(ds)


def hit_month(paths):
    """その月の results を読み、(行の配列, 最初の日, 最後の日) を返す。読めない日があれば None。"""
    rows = []
    days = []
    for path in paths:
        hd = os.path.basename(path)[:8]
        try:
            d = json.load(io.open(path, encoding="utf-8"))
            races = d.get("結果", []) or []
            day_rows = []
            for r in races:
                p = r.get("払戻") or {}
                row = [hd[6:8], int(str(r.get("場コード", "0"))), race_no(r)]
                for t in HIT_TYPES:
                    lst = []
                    for x in p.get(t, []) or []:
                        c = hit_combo(t, x.get("組番", ""))
                        v = x.get("配当")
                        if c and isinstance(v, int) and v > 0:
                            lst.append([c, v])
                    row.append(lst)
                day_rows.append(row)
        except Exception as e:
            print("hit skip month: unreadable", hd, e)
            return None
        if day_rows:
            rows.extend(day_rows)
            days.append(hd)
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    if not days:
        return [], None, None
    return rows, days[0], days[-1]


def build_hit(all_paths):
    os.makedirs(HIT_DIR, exist_ok=True)
    today = os.path.basename(all_paths[-1])[:8] if all_paths else None
    done = all_paths[:-1]
    by_month = {}
    for p in done:
        by_month.setdefault(os.path.basename(p)[:6], []).append(p)
    recent = set(os.path.basename(p)[:6] for p in done[-SITE_DAYS:])
    months = []
    for ym in sorted(by_month.keys()):
        out = os.path.join(HIT_DIR, "%s.json" % ym)
        meta = None
        if ym in recent or not os.path.exists(out):
            got = hit_month(by_month[ym])
            if got is not None and got[1]:
                rows, first, last = got
                body = {"月": ym, "券種": HIT_TYPES, "最初": first, "最後": last,
                        "レース数": len(rows), "レース": rows}
                text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
                old = None
                if os.path.exists(out):
                    old = io.open(out, encoding="utf-8").read()
                if old != text:
                    with io.open(out, "w", encoding="utf-8") as f:
                        f.write(text)
                meta = {"月": ym, "最初": first, "最後": last, "レース数": len(rows)}
        if meta is None and os.path.exists(out):
            try:
                o = json.load(io.open(out, encoding="utf-8"))
                meta = {"月": ym, "最初": o["最初"], "最後": o["最後"], "レース数": o["レース数"]}
            except Exception as e:
                print("hit index skip", ym, e)
        if meta:
            months.append(meta)
    months.sort(key=lambda x: x["月"], reverse=True)
    idx = {"券種": HIT_TYPES,
           "最初": months[-1]["最初"] if months else None,
           "最後": months[0]["最後"] if months else None,
           "レース数": sum(m["レース数"] for m in months),
           "当日": today,
           "月": months}
    with io.open(os.path.join(HIT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))
    print("hit wrote", len(months), "months", idx["レース数"], "races")


if __name__ == "__main__":
    main()
