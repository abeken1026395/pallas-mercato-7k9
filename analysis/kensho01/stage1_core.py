# stage1.py の集計部分（contrast 以降を除いた写し）。stage2 が読み込む。
# -*- coding: utf-8 -*-
"""検証01 stage1：design.md の固定どおりに数える。入力は stage0 の出力と rankHistory.json（読むだけ）。
出力は kensho01parts/s1.json のみ。"""
import bisect
import zlib
import json
from collections import defaultdict

import numpy as np

D = "C:/Users/USER/kensho01parts/"
PTS = {1: 10, 2: 8, 3: 6, 4: 4, 5: 2, 6: 1}
SEED = 20260922
NPERM = 1000
MASK = (1 << 64) - 1


def splitmix64(x):
    x = (x + 0x9E3779B97F4A7C15) & MASK
    z = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31)


def rng(key):
    return np.random.Generator(np.random.PCG64(splitmix64((SEED ^ key) & MASK)))


month = {}
for k, v in json.load(open(D + "s0_month.json", encoding="utf-8")).items():
    t, ym = k.split("|")
    month[(t, ym)] = v
rh = json.load(open("C:/Users/USER/bfiles/rankHistory.json", encoding="utf-8"))
RIDX = {t: ([c[0] for c in v["changes"]], [c[1] for c in v["changes"]]) for t, v in rh.items()}


def kyu(t, h8):
    e = RIDX.get(t)
    if not e:
        return "?"
    day = "%s-%s-%s" % (h8[:4], h8[4:6], h8[6:])
    i = bisect.bisect_right(e[0], day) - 1
    return e[1][i][:1] if i >= 0 else "?"


def prev_months(ym, n=12):
    y, m = int(ym[:4]), int(ym[4:])
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y -= 1; m = 12
        out.append("%04d%02d" % (y, m))
    return out


def strength(t, h8):
    s = c = 0
    for ym in prev_months(h8[:6]):
        v = month.get((t, ym))
        if v:
            s += v[0]; c += v[1]
    return (s / c) if c >= 30 else None


def band(g):
    if g < -2: return "もう届かない"
    if g < -0.5: return "圏外"
    if g <= 0.5: return "崖っぷち"
    if g <= 2: return "やや圏内"
    return "安全圏"


BANDS = ["もう届かない", "圏外", "崖っぷち", "やや圏内", "安全圏"]
rows = []          # 選手×最終日
ex = defaultdict(int)
gaptab = defaultdict(lambda: [0, 0])
for line in open(D + "s0_setsu.jsonl", encoding="utf-8"):
    s = json.loads(line)
    fd = s["fd"]
    for r in s["racers"]:
        if r["nB"] == 0:
            ex["最終日の前に走っていない"] += 1
            continue
        if r["badB"]:
            ex["最終日の前にF・妨害で順位外"] += 1
            continue
        if not r["fin"]:
            ex["最終日に走っていない"] += 1
            continue
        g = r["gap"]
        b = band(g)
        # ボーダーとの差の表（元の表の帯）
        for lo, hi, lab in ((-99, -2, "−2.0未満"), (-2, -1, "−2.0から−1.0"), (-1, -0.5, "−1.0から−0.5"),
                            (-0.5, 0, "−0.5から0.0"), (0, 0.5, "0.0から+0.5"), (0.5, 1, "+0.5から+1.0"),
                            (1, 2, "+1.0から+2.0"), (2, 99, "+2.0超")):
            if lo <= g < hi or (hi == 99 and g >= lo):
                gaptab[lab][0] += 1; gaptab[lab][1] += r["adv"]
                break
        rows.append({"t": r["t"], "v": s["v"], "fd": fd, "yr": fd[:4], "gap": g, "band": b, "rateB": r["rateB"],
                     "adv": r["adv"], "fin": r["fin"], "str": strength(r["t"], fd), "kyu": kyu(r["t"], fd)})

sv = sorted(x["str"] for x in rows if x["str"] is not None)
qs = [sv[int(len(sv) * q / 5)] for q in (1, 2, 3, 4)]


def s5(x):
    if x is None:
        return -1
    return bisect.bisect_right(qs, x)


for x in rows:
    x["s5"] = s5(x["str"])

# レースごとの層の平均（枠×強さ×年）と、STの層（進入×強さ×年）
agg = defaultdict(lambda: [0.0, 0]); aggst = defaultdict(lambda: [0.0, 0])
wk = defaultdict(lambda: [0.0, 0])
for x in rows:
    for f in x["fin"]:
        c = f["c"]
        if c.isdigit() and 1 <= int(c) <= 6 and f["w"]:
            p = PTS[int(c)]
            a = agg[(f["w"], x["s5"], x["yr"])]; a[0] += p; a[1] += 1
            w = wk[f["w"]]; w[0] += p; w[1] += 1
        try:
            st = float(f["st"])
        except ValueError:
            st = None
        if st is not None and f["sh"].isdigit():
            a = aggst[(f["sh"], x["s5"], x["yr"])]; a[0] += st; a[1] += 1

wavg = {w: v[0] / v[1] for w, v in wk.items()}
step = np.mean([wavg[w] - wavg[w + 1] for w in range(1, 6)])

for x in rows:
    res = []; resst = []; raw = []; nf = 0; nrace = 0
    for f in x["fin"]:
        nrace += 1
        c = f["c"]
        if c == "F":
            nf += 1
        if c.isdigit() and 1 <= int(c) <= 6 and f["w"]:
            p = PTS[int(c)]
            a = agg[(f["w"], x["s5"], x["yr"])]
            res.append(p - a[0] / a[1]); raw.append(p + f["bn"])
        try:
            st = float(f["st"])
        except ValueError:
            st = None
        if st is not None and f["sh"].isdigit():
            a = aggst[(f["sh"], x["s5"], x["yr"])]
            resst.append(st - a[0] / a[1])
    x["res"] = float(np.mean(res)) if res else None
    x["resst"] = float(np.mean(resst)) if resst else None
    x["rise"] = (float(np.mean(raw)) - x["rateB"]) if raw else None
    x["nf"] = nf; x["nrace"] = nrace


