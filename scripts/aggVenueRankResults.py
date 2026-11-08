"""aggVenueRankResults.py — 24場を数字で並べる（results 版の集計）。出力の形は aggVenueRank10y.py と同じ（風は無し）
使い方: python3 scripts/aggVenueRankResults.py <リポジトリのルート> <出力JSON> [最終日YYYYMMDD]
"""
import json, glob, os, sys, collections

ROOT, OUT = sys.argv[1], sys.argv[2]
END = sys.argv[3] if len(sys.argv) > 3 else "20261107"
VENUES = [f"{i:02d}" for i in range(1, 25)]
RATE = ("c1", "c4", "man", "shin")
MEAN = ("wind", "wave")


def season(m):
    return "冬" if m in (12, 1, 2) else "夏" if m in (6, 7, 8) else None


def period_key(d8):
    y, m = int(d8[:4]), int(d8[4:6])
    return f"{y}Q{(m - 1) // 3 + 1}"


rate = collections.defaultdict(lambda: [0, 0])          # (key, v, p) -> [num, den]
mean = collections.defaultdict(lambda: [0.0, 0, 0.0])   # (key, v, p) -> [sum, n, sumsq]
grade = collections.defaultdict(lambda: [0, 0])         # (v, g) -> [win, n]
seas = collections.defaultdict(lambda: [0, 0])          # (v, s) -> [win, n]
days, gdays = [], []

for f in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))):
    d8 = os.path.basename(f)[:8]
    if d8 > END:
        continue
    days.append(d8)
    p = period_key(d8)
    s = season(int(d8[4:6]))
    data = json.load(open(f, encoding="utf-8"))
    has_grade = False
    for r in data.get("結果", []):
        v = r.get("場コード")
        if v not in VENUES:
            continue
        boats = [b for b in r.get("艇", []) if b.get("着") != 16 and isinstance(b.get("コース"), int)]
        if len(boats) < 5:
            continue

        def addr(k, x):
            for q in ("ALL", p):
                c = rate[(k, v, q)]; c[0] += x; c[1] += 1

        def addm(k, x):
            for q in ("ALL", p):
                c = mean[(k, v, q)]; c[0] += x; c[1] += 1; c[2] += x * x

        for b in boats:
            win = 1 if b.get("着") == 1 else 0
            if b["コース"] == 1:
                addr("c1", win)
                if s:
                    seas[(v, s)][0] += win; seas[(v, s)][1] += 1
                g = b.get("級別")
                if g in ("A1", "A2", "B1", "B2"):
                    has_grade = True
                    grade[(v, g)][0] += win; grade[(v, g)][1] += 1
            if b["コース"] == 4:
                addr("c4", win)
        pay = r.get("三連単配当")
        if isinstance(pay, int) and pay > 0:
            addr("man", 1 if pay >= 10000 else 0)
        order = [b["枠"] for b in sorted(boats, key=lambda b: b["コース"])]
        addr("shin", 0 if order == sorted(order) else 1)
        if isinstance(r.get("風速"), (int, float)):
            addm("wind", r["風速"])
        if isinstance(r.get("波高"), (int, float)):
            addm("wave", r["波高"])
    if has_grade:
        gdays.append(d8)

periods = sorted({period_key(d) for d in days})
out = {
    "出典": "results/（公式 競走成績）",
    "期間": [days[0], days[-1]],
    "区切り": "四半期",
    "区切り一覧": periods,
    "レース数": sum(rate[("shin", v, "ALL")][1] for v in VENUES),
    "定義": "欠場（着16）を除く。5艇未満のレースは除く。級別は results に級別がある日だけ",
    "指標": {},
    "級別": {"期間": [gdays[0], gdays[-1]] if gdays else None, "場": {}},
    "季節": {"冬の月": [12, 1, 2], "夏の月": [6, 7, 8], "場": {}},
    "風": None,
}
for k in RATE:
    out["指標"][k] = {"型": "率", "場": {v: rate[(k, v, "ALL")] for v in VENUES},
                     "区切り": {v: {q: rate[(k, v, q)] for q in periods} for v in VENUES}}
for k in MEAN:
    out["指標"][k] = {"型": "平均", "場": {v: mean[(k, v, "ALL")] for v in VENUES},
                     "区切り": {v: {q: mean[(k, v, q)] for q in periods} for v in VENUES}}
for v in VENUES:
    out["級別"]["場"][v] = {g: grade[(v, g)] for g in ("A1", "A2", "B1", "B2")}
    out["季節"]["場"][v] = {s: seas[(v, s)] for s in ("冬", "夏")}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("集計", out["期間"], "レース", out["レース数"], "級別期間", out["級別"]["期間"], "区切り", periods)
