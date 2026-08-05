# -*- coding: utf-8 -*-
# buildOdds.py
# turnmark/api(GitHub Pages配信)から全24場・全レースのオッズを抽出し
# odds/YYYYMMDD.json に出力。
#
# 取得元: https://raw.githubusercontent.com/turnmark/api/gh-pages/docs/v1/YYYY/YYYYMMDD.json
#   ・turnmark は「前日までのデータ」しか出さない。当日日付は404。実測では、ある日の
#     ファイルは翌朝(JST 05:30頃)に1回だけ書かれ、その後は更新されない。
#     したがって日中に叩いても当日分は取れず、取得は翌朝以降に1回で足りる。
#   ・対応期間は2026-01-01以降。それ以前は404。
#   ・boatraceopenapi/api(結果・直前情報)とは別リポジトリ。あちらは当日分を約3分間隔で
#     更新するがオッズを持たない。オッズが要るのでこちらを併用する。
#
# オッズの性質(実測・2026-05-01の172レースで確定払戻と突合):
#   ・3連単オッズ×100 と確定払戻が一致したのは167レース。1レースは丸め差、
#     4レース(2.3%)は20%以上乖離した。
#   ・つまりこれは締切前のある時点のスナップショット1点であり、確定オッズではない。
#     日次ファイルが1回しか書かれないため、オッズの時系列推移は取れない。
#   ・この性質を「注記」キーとしてファイル自身に持たせる。数字だけが独り歩きして
#     払戻の代替に使われることを防ぐ。
#
# 保存方針: APIの生キー・生の値をそのまま保持する。
#   ・改名・単位変換・丸め・式別の間引きは一切しない。
#   ・場コード・レースの2キーだけを、results/ preview/ と同じ表記で付加する。
#   ・出力は最小化(区切り文字を詰める)。3連単だけで120通りあり容量が大きいため。
#   ・odds に無いレースは行を作らない。
#
# 書き込みの省略:
#   ・既存ファイルと「取得時刻」以外が同一なら書かない。2便とも同じ日を取りに行くため、
#     不変の日を書き直し続けるとリポジトリ容量が積み上がり、git log からデータが
#     実際に変わった時点を追えなくなるため。
#   ・省いた場合も必ずログに出す。無言で何もしないと、止まっているのか
#     不変なのか判別できなくなる。
#
# 本番: 環境変数なしで「前日から遡ってN日」(既定2)を取得。当日は取れないので含めない。
# 複数日: 環境変数 HD にカンマ区切りで日付(YYYYMMDD)を渡すと全日ぶん取得。
import io
import os
import json
import time
import datetime
import urllib.request

BASE = "https://raw.githubusercontent.com/turnmark/api/gh-pages/docs/v1/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) boatrace-data-collector"

NOTE = "締切前の時点値。確定オッズではない。払戻の代替に使わない"


def fetch_json(hd):
    """指定日(YYYYMMDD)のJSONを取得してdictで返す。404/失敗はNone。"""
    y = hd[:4]
    url = "{0}{1}/{2}.json".format(BASE, y, hd)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except Exception:
        return None
    if not raw or len(raw) < 20:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def to_odds(data):
    """v1のprograms/stadiums/racesから odds セクションを抜き出して配列にする。
    キー・値はAPIの生のまま。"""
    rows = []
    stadiums = ((data.get("programs") or {}).get("stadiums") or {})
    for sn in sorted(stadiums, key=lambda x: int(x)):
        rmap = (stadiums[sn] or {}).get("races") or {}
        for rn in sorted(rmap, key=lambda x: int(x)):
            od = (rmap[rn] or {}).get("odds")
            if not od:
                continue
            try:
                row = {
                    "場コード": "%02d" % int(od["stadium_number"]),
                    "レース": "%dR" % int(od["race_number"]),
                }
                for k in od:
                    row[k] = od[k]
                rows.append(row)
            except Exception:
                continue
    return rows


def _unchanged(outpath, obj):
    """既存ファイルと「取得時刻」以外が同一ならTrueを返す（＝書き込みを省く）。
    ファイルが無い・壊れている・JSONとして読めない場合はFalse（＝書き直す）。
    文字列でなくJSONとして読んでdictで比較する。キー順や空白の揺れで
    誤って「変わった」と判定するのを避けるため。"""
    try:
        with io.open(outpath, "r", encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        return False
    if not isinstance(old, dict):
        return False
    a = dict((k, v) for k, v in old.items() if k != "取得時刻")
    b = dict((k, v) for k, v in obj.items() if k != "取得時刻")
    return a == b


def write_odds(data, hd):
    rows = to_odds(data)
    venues = len(set(x["場コード"] for x in rows))
    os.makedirs("odds", exist_ok=True)
    outpath = os.path.join("odds", "%s.json" % hd)
    obj = {"開催日": hd,
           "取得時刻": datetime.datetime.now().isoformat(timespec="seconds"),
           "注記": NOTE,
           "レース数": len(rows),
           "オッズ": rows}
    if _unchanged(outpath, obj):
        print("unchanged", outpath, "(取得時刻以外に差分なし・書き込みスキップ)")
        return len(rows)
    with io.open(outpath, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote", outpath, "races", len(rows), "venues", venues)
    return len(rows)


def main():
    hd_env = os.environ.get("HD", "").strip()
    if hd_env:
        days = [x.strip() for x in hd_env.replace("\u3001", ",").split(",") if x.strip()]
    else:
        # 前日から遡ってN日(既定2)。turnmarkは当日分を持たないため当日は含めない。
        # 2日にしているのは、スケジュール遅延で発火が日付境界を越えたときに
        # 前日分を取りこぼさないため。再取得は冪等(同一データで上書き)。
        win = max(1, int(os.environ.get("ODDS_WINDOW", "2")))
        today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
        days = [(today - datetime.timedelta(days=i + 1)).strftime("%Y%m%d") for i in range(win)]

    for hd in days:
        data = fetch_json(hd)
        if not data:
            print("no data for", hd)
            continue
        write_odds(data, hd)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
