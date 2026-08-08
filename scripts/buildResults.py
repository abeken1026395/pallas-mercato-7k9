# -*- coding: utf-8 -*-
# buildResults.py
# boatraceopenapi/api(GitHub Pages配信)から全24場・全レースの
# 着順(組番)・決まり手・全式別払戻を抽出し results/YYYYMMDD.json に出力。
# 見立て検証(verifyPredictions.py)の結果側データ、および結果表ページ(docs/results/)の元データ。
#
# 取得元: https://raw.githubusercontent.com/boatraceopenapi/api/gh-pages/docs/v1/YYYY/YYYYMMDD.json
#   ・旧取得元 BoatraceOpenAPI/results v2 は非推奨宣言済み。後継の boatraceopenapi/api v1 へ移行。
#     v1は約3分間隔で更新され、当日分もレース確定ごとに追記される。対応期間は2026-01-01以降。
#   ・2025-07-15〜2025-12-31 の results/*.json は v1 に存在しない期間のため、既存ファイルを残置する。
#     本スクリプトは指定日ぶんのみを書き出し、既存の他日ファイルには触れない。
#   ・GitHub配信のためGitHub ActionsのIPからも通る(mbraceのIPブロック問題を回避)。
#   ・当日結果はレース確定後に反映。未確定/非開催日は404。
#   ・v1には決まり手(technique_number)と全式別払戻(trifecta/trio/exacta/
#     quinella/quinella_place/win/place)が含まれるため mbrace LZH は不要。
#   ・レース単位の実測条件(風速/風向/波高/天候/気温/水温)も含まれる。これらは
#     weather.json(Open-Meteoの予報値)と違い、レース時点の実測値。現時点で用途は
#     決めていないが、過去に遡れる保証がないため取得できるものは全項目保存する。
#     風向・天候はAPIがコード値で返す。変換は表示側の役割とし、ここでは生値のまま持つ。
#   ・v1のpayoutsは配当額のキーが amount(v2は payout)。出力形式は従来どおり。
#   ・v1のracersには級別(rank_number_source="A1"等 / rank_number=1〜4)がある。これは
#     レース当時の級別なので、期首固定の現在値(docs/data/racerStatsCore.json)と違い
#     過去のレースにも当時の事実が出る。生値とコードの両方を保存する。
#     2025-07-15〜2025-12-31 の既存ファイルは旧取得元(v2)由来で rank 系を持たないため、
#     この期間の級別は入らない(取れなかったものは埋めない)。
#
# 本番: 環境変数なしで当日(JST)分を取得。
# 複数日: 環境変数 HD にカンマ区切りで日付(YYYYMMDD)を渡すと全日ぶん取得(過去分の穴埋め用)。
import io
import os
import json
import time
import datetime
import urllib.request

BASE = "https://raw.githubusercontent.com/boatraceopenapi/api/gh-pages/docs/v1/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) boatrace-data-collector"

# 決まり手コード(technique_number) → 表記
TECHNIQUE = {
    1: "逃げ", 2: "差し", 3: "まくり",
    4: "まくり差し", 5: "抜き", 6: "恵まれ",
}


def _payouts(payouts):
    """OpenAPIのpayoutsを、式別ごとの[{組番,配当}...]に整形して返す。
    単勝/複勝/2連単/2連複/拡連複/3連複/3連単の順。配当欠損は0/Noneを除外。"""
    # OpenAPIキー → 日本語式別名
    mapping = [
        ("win", "単勝"),
        ("place", "複勝"),
        ("exacta", "2連単"),
        ("quinella", "2連複"),
        ("quinella_place", "拡連複"),
        ("trio", "3連複"),
        ("trifecta", "3連単"),
    ]
    out = {}
    for key, label in mapping:
        rows = []
        for e in payouts.get(key, []) or []:
            combo = e.get("combination")
            pay = e.get("amount")
            if not combo or pay in (None, 0):
                continue
            try:
                rows.append({"組番": combo, "配当": int(pay)})
            except Exception:
                continue
        out[label] = rows
    return out


def fetch_json(hd):
    """指定日(YYYYMMDD)の結果JSONを取得してdictで返す。404/失敗はNone。"""
    y = hd[:4]
    url = "{0}{1}/{2}.json".format(BASE, y, hd)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
    except Exception:
        return None
    if not raw or len(raw) < 20:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def to_races(data):
    """後継API(v1)のprograms/stadiums/racesを、既存results形式のレース配列に変換。"""
    races = []
    stadiums = ((data.get("programs") or {}).get("stadiums") or {})
    for sn in sorted(stadiums, key=lambda x: int(x)):
        rmap = (stadiums[sn] or {}).get("races") or {}
        for rn in sorted(rmap, key=lambda x: int(x)):
            res = (rmap[rn] or {}).get("result")
            if not res:
                continue
            payouts = res.get("payouts") or {}
            tri = payouts.get("trifecta") or []
            if not tri:
                continue
            combo = tri[0].get("combination")
            pay = tri[0].get("amount")
            if not combo or pay in (None, 0):
                continue
            top3 = combo.split("-")
            if len(top3) != 3:
                continue
            try:
                boats = []
                racers = res.get("racers") or {}
                for en in sorted(racers, key=lambda x: int(x)):
                    b = racers[en] or {}
                    boats.append({
                        "枠": b.get("entry_number"),
                        "登番": b.get("number"),
                        "氏名": b.get("name"),
                        "コース": b.get("course_number"),
                        "ST": b.get("start_timing"),
                        "着": b.get("place_number"),
                        "級別": b.get("rank_number_source"),
                        "級別コード": b.get("rank_number"),
                    })
                tech_no = res.get("technique_number")
                try:
                    tech_no = int(tech_no) if tech_no is not None else None
                except Exception:
                    tech_no = None
                races.append({
                    "場コード": "%02d" % int(res["stadium_number"]),
                    "レース": "%dR" % int(res["race_number"]),
                    "着順": combo,
                    "1着": int(top3[0]), "2着": int(top3[1]), "3着": int(top3[2]),
                    "三連単配当": int(pay),
                    "決まり手": TECHNIQUE.get(tech_no),
                    "払戻": _payouts(payouts),
                    "艇": boats,
                    "レース日": res.get("date"),
                    "風速": res.get("wind_speed"),
                    "風向コード": res.get("wind_direction_number"),
                    "波高": res.get("wave_height"),
                    "天候コード": res.get("weather_number"),
                    "気温": res.get("air_temperature"),
                    "水温": res.get("water_temperature"),
                })
            except Exception:
                continue
    return races


def write_results(data, hd):
    races = to_races(data)
    venues = len(set(x["場コード"] for x in races))
    os.makedirs("results", exist_ok=True)
    outpath = os.path.join("results", "%s.json" % hd)
    obj = {"開催日": hd,
           "取得時刻": datetime.datetime.now().isoformat(timespec="seconds"),
           "レース数": len(races), "結果": races}
    with io.open(outpath, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print("wrote", outpath, "races", len(races), "venues", venues)
    return len(races)


def main():
    hd_env = os.environ.get("HD", "").strip()
    if hd_env:
        days = [x.strip() for x in hd_env.replace("\u3001", ",").split(",") if x.strip()]
    else:
        # \u76f4\u8fd1N\u65e5\u306e\u7a93\uff08\u65e2\u5b9a3\uff09\u3067\u53d6\u5f97\u3002GitHub Actions\u306e\u30b9\u30b1\u30b8\u30e5\u30fc\u30eb\u9045\u5ef6\u3067\u767a\u706b\u304c
        # JST\u65e9\u671d\u306b\u305a\u308c\u8fbc\u307f\u300c\u5f53\u65e5\u306e\u307f\u300d\u3060\u3068\u7d42\u4e86\u76f4\u5f8c\u306e\u65e5\u3092\u90e8\u5206\u53d6\u5f97\u306e\u307e\u307e\u53d6\u308a\u3053\u307c\u3059\u554f\u984c\u3078\u306e\u5bfe\u7b56\u3002
        # \u30df\u30e9\u30fc\u306f\u78ba\u5b9a\u65e5\u306e\u5168\u7d50\u679c\u3092\u6301\u3064\u305f\u3081\u3001\u518d\u53d6\u5f97\u306f\u51aa\u7b49\uff08\u540c\u4e00\u30c7\u30fc\u30bf\u3067\u4e0a\u66f8\u304d\uff09\u3002
        win = max(1, int(os.environ.get("RESULTS_WINDOW", "3")))
        today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
        days = [(today - datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(win)]

    for hd in days:
        data = fetch_json(hd)
        if not data:
            print("no data for", hd)
            continue
        write_results(data, hd)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
