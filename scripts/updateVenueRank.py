# -*- coding: utf-8 -*-
"""updateVenueRank.py — 24場番付の集計を、Kファイル10年版の土台に results の新しい日を足して作り直す

使い方
  python3 scripts/updateVenueRank.py [最終日YYYYMMDD]
    最終日を省くと「JSTの昨日」まで（その日の results がまだ揃っていないことがあるため今日は入れない）

入力  analysis/venueRank/venueRank10y.json（Kファイル由来の土台。書き換えない）
      results/YYYYMMDD.json（土台の最終日の翌日から最終日まで）
出力  analysis/venueRank/venueRankLive.json（土台＋足した分。毎回まるごと作り直す）

決まりは aggVenueRank10y.py と同じ（Agg をそのまま使う）。results の違いだけ埋める
  欠場は着16。級別は results の「級別」を優先（無い日は rankHistory.json）
  風向きは風向コード（吹いていく方位・17=無風）の角度をそのまま使う（Kファイルの回転と同じ向き）
足す日が0日なら土台をそのまま書く。
"""
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from aggVenueRank10y import Agg, VENUES  # noqa: E402

BASE = os.path.join(ROOT, "analysis", "venueRank", "venueRank10y.json")
OUT = os.path.join(ROOT, "analysis", "venueRank", "venueRankLive.json")


def add_cell(a, b):
    return [x + y for x, y in zip(a, b)]


def merge(base, inc):
    o = json.loads(json.dumps(base))
    if not inc:
        return o
    years = sorted(set(base["区切り一覧"]) | set(inc["区切り一覧"]))
    o["期間"] = [base["期間"][0], inc["期間"][1]]
    o["区切り一覧"] = years
    o["レース数"] = base["レース数"] + inc["レース数"]
    o["出典"] = "Kファイル（%s から %s）＋ results（%s から %s）・どちらも BOAT RACE 公式の競走成績" % (
        base["期間"][0], base["期間"][1], inc["期間"][0], inc["期間"][1])
    for k, m in o["指標"].items():
        zero = [0.0, 0, 0.0] if m["型"] == "平均" else [0, 0]
        for v in VENUES:
            m["場"][v] = add_cell(m["場"][v], inc["指標"][k]["場"][v])
            for y in years:
                a = m["区切り"][v].get(y, zero)
                b = inc["指標"][k]["区切り"][v].get(y, zero)
                m["区切り"][v][y] = add_cell(a, b)
    o["級別"]["期間"] = [base["級別"]["期間"][0], inc["期間"][1]]
    for sec in ("級別", "季節", "風"):
        for v in VENUES:
            for c in o[sec]["場"][v]:
                o[sec]["場"][v][c] = add_cell(o[sec]["場"][v][c], inc[sec]["場"][v][c])
    o["風"]["方位不明"] = base["風"]["方位不明"] + inc["風"]["方位不明"]
    return o


def results_agg(start, end):
    agg = Agg()
    n = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))):
        d8 = os.path.basename(f)[:8]
        if not d8.isdigit() or d8 < start or d8 > end:
            continue
        n += 1
        data = json.load(open(f, encoding="utf-8"))
        for r in data.get("結果", []):
            ents = []
            for b in r.get("艇", []):
                ch = b.get("着")
                ents.append({"chaku": "K0" if ch == 16 else ("%02d" % ch if isinstance(ch, int) and 1 <= ch <= 6 else str(ch)),
                             "waku": str(b.get("枠", "")), "shinnyu": str(b.get("コース", "")),
                             "toban": b.get("登番"), "grade": b.get("級別")})
            wc = r.get("風向コード")
            rinfo = {"windMps": "%sm" % r["風速"] if isinstance(r.get("風速"), (int, float)) else "",
                     "waveCm": "%scm" % r["波高"] if isinstance(r.get("波高"), (int, float)) else "",
                     "windDir": "無風" if wc == 17 else ""}
            if isinstance(wc, int) and 1 <= wc <= 16:
                rinfo["windAngle"] = (wc - 1) * 22.5
            pay = r.get("三連単配当")
            agg.race(d8, r.get("場コード"), rinfo, ents, pay if isinstance(pay, int) else None)
    if not agg.days:
        return None, n
    return agg.result("results"), n


def main():
    if len(sys.argv) > 1:
        end = sys.argv[1]
    else:
        end = (datetime.now(timezone(timedelta(hours=9))) - timedelta(days=1)).strftime("%Y%m%d")
    base = json.load(open(BASE, encoding="utf-8"))
    start = (datetime.strptime(base["期間"][1], "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    inc, nfile = results_agg(start, end) if start <= end else (None, 0)
    o = merge(base, inc)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, separators=(",", ":"))
    print("土台", base["期間"], base["レース数"], "足した日", start, "から", end, "ファイル", nfile,
          "足したレース", inc["レース数"] if inc else 0, "→", o["期間"], o["レース数"])


if __name__ == "__main__":
    main()
