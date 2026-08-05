# -*- coding: utf-8 -*-
# buildPreview.py
# boatraceopenapi/api(GitHub Pages配信)から全24場・全レースの直前情報(preview)を
# 抽出し preview/YYYYMMDD.json に出力。
#
# 取得元: https://raw.githubusercontent.com/boatraceopenapi/api/gh-pages/docs/v1/YYYY/YYYYMMDD.json
#   ・buildResults.py と同じファイルを読む。あちらは result セクション、こちらは preview セクション。
#     結果は確定後に増えるが直前情報は締切前に確定する別ライフサイクルのため、WFも別に持つ。
#   ・対応期間は2026-01-01以降。それ以前は404。
#   ・展示タイム(exhibition_time)は精度向上モデルの変数 tenjiDev1 の素材。
#     欠測は null のまま保存し、率を出す側で分母(有効件数)を必ず併記すること。
#     実測(2026-01-01〜2026-08-04・202,608枠)の充填率は98.4%。欠測の9割は
#     「その日・その場」が丸ごと空く形で、残りは欠場艇。
#
# 保存方針: APIの生キーをそのまま保持する(_source付きの原文も含む)。
#   ・改名・単位変換・コード値の読み替えは一切しない。表示側の役割とする。
#   ・場コード・レースの2キーだけを、results/YYYYMMDD.json と同じ表記で付加する。
#   ・preview に無いレース(直前情報未発表・中止等)は行を作らない。
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


def fetch_json(hd):
    """指定日(YYYYMMDD)のJSONを取得してdictで返す。404/失敗はNone。"""
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


def to_previews(data):
    """v1のprograms/stadiums/racesから preview セクションを抜き出して配列にする。
    キーはAPIの生のまま。racersだけ entry_number 昇順の配列に直す。"""
    rows = []
    stadiums = ((data.get("programs") or {}).get("stadiums") or {})
    for sn in sorted(stadiums, key=lambda x: int(x)):
        rmap = (stadiums[sn] or {}).get("races") or {}
        for rn in sorted(rmap, key=lambda x: int(x)):
            pv = (rmap[rn] or {}).get("preview")
            if not pv:
                continue
            try:
                row = {
                    "場コード": "%02d" % int(pv["stadium_number"]),
                    "レース": "%dR" % int(pv["race_number"]),
                }
                for k in pv:
                    if k == "racers":
                        continue
                    row[k] = pv[k]
                racers = pv.get("racers") or {}
                boats = []
                for en in sorted(racers, key=lambda x: int(x)):
                    b = racers[en] or {}
                    boats.append(dict(b))
                row["racers"] = boats
                rows.append(row)
            except Exception:
                continue
    return rows


def write_previews(data, hd):
    rows = to_previews(data)
    venues = len(set(x["場コード"] for x in rows))
    slots = sum(len(x.get("racers") or []) for x in rows)
    filled = 0
    for x in rows:
        for b in (x.get("racers") or []):
            if b.get("exhibition_time") is not None:
                filled += 1
    os.makedirs("preview", exist_ok=True)
    outpath = os.path.join("preview", "%s.json" % hd)
    obj = {"開催日": hd,
           "取得時刻": datetime.datetime.now().isoformat(timespec="seconds"),
           "レース数": len(rows),
           "展示タイム有効数": filled,
           "展示タイム枠数": slots,
           "直前情報": rows}
    with io.open(outpath, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print("wrote", outpath, "races", len(rows), "venues", venues,
          "exhibition", "%d/%d" % (filled, slots))
    return len(rows)


def main():
    hd_env = os.environ.get("HD", "").strip()
    if hd_env:
        days = [x.strip() for x in hd_env.replace("\u3001", ",").split(",") if x.strip()]
    else:
        # 直近N日の窓(既定3)で取得。GitHub Actionsのスケジュール遅延で発火がJST早朝に
        # ずれ込み、当日のみだと直前情報を取りこぼす問題への対策。再取得は冪等。
        win = max(1, int(os.environ.get("PREVIEW_WINDOW", "3")))
        today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
        days = [(today - datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(win)]

    for hd in days:
        data = fetch_json(hd)
        if not data:
            print("no data for", hd)
            continue
        write_previews(data, hd)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
