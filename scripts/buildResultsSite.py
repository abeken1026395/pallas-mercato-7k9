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


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # 元データ results/ は全期間そのまま読み、公開するのは新しい方から SITE_DAYS 日分だけ。
    paths = sorted(
        p for p in glob.glob(os.path.join(SRC_DIR, "*.json"))
        if re.match(r"^\d{8}$", os.path.basename(p)[:8])
    )
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


if __name__ == "__main__":
    main()
