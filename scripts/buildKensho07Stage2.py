# -*- coding: utf-8 -*-
# buildKensho07Stage2.py
# 検証07 -- stage2：冬夏差を、1コースの選手の強さ別と、外5艇の強さ別に割る。
#
# 使い方
#   py scripts\buildKensho07Stage2.py
#
# 入力 : stage1 が PARTS_DIR に書いた s1r2016.csv から s1r2026.csv（読むだけ）
#        analysis/kensho07/stage1.json（全体の差の照合に使う）
# 出力 : analysis/kensho07/stage2.json
#
# 層と置換は stage1 と同じ（buildKensho07Stage1.py の関数をそのまま使う）。
# 全体の差が stage1 と一致しなければ何も書かずに止まる。
import os
import io
import sys
import csv
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import buildKensho07Stage1 as s1  # noqa: E402

ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "analysis", "kensho07")
STAGE1 = os.path.join(OUTDIR, "stage1.json")
C1_BINS = ["new", "lt15", "15to25", "25to35", "ge35"]
OUT_BINS = ["na", "lt12", "12to15", "15to18", "ge18"]


def build_strata():
    racers = {}
    strata = {}
    total = 0
    last_mi = None
    for y in s1.YEARS:
        p = os.path.join(s1.PARTS_DIR, "s1r%s.csv" % y)
        if not os.path.exists(p):
            s1.stop("rows の中間ファイルが無い: s1r%s.csv" % y)
        with io.open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                total += 1
                hd = r["hd"]
                mi = s1.month_index(hd)
                month = int(hd[4:6])
                if last_mi is not None and mi != last_mi and mi % 6 == 0:
                    for rc in racers.values():
                        rc.trim(mi)
                last_mi = mi
                tob = [r["t%d" % c] for c in range(1, 7)]
                rates = []
                for t in tob:
                    rc = racers.get(t) if t else None
                    rates.append(rc.prior_rate(mi) if rc else None)
                cb = s1.c1_bin(rates[0])
                ob = s1.out_bin(rates[1:])
                win1 = 1 if r["winCourse"] == "1" else 0
                season = s1.season_of(month)
                sy = int(hd[:4]) + (1 if month == 12 else 0)
                if season:
                    key = "%s|%d|%s|%s|%s" % (r["jcd"], sy, r["rclass"], cb, ob)
                    c = strata.get(key)
                    if c is None:
                        c = [0, 0, 0, 0]
                        strata[key] = c
                    if season == "W":
                        c[0] += 1
                        c[1] += win1
                    else:
                        c[2] += 1
                        c[3] += win1
                for pos, t in enumerate(tob):
                    if not t:
                        continue
                    rc = racers.get(t)
                    if rc is None:
                        rc = s1.Racer()
                        racers[t] = rc
                    rc.add(mi, 1 if (pos + 1) == int(r["winCourse"]) else 0)
        print("  strata %s done races=%d" % (y, total))
        sys.stdout.flush()
    return strata, total


def test_cells(strata, keys):
    import numpy as np
    cells = [tuple(strata[k]) for k in keys]
    d_obs, wsum = s1.cmh_diff(cells)
    nW = sum(c[0] for c in cells)
    kW = sum(c[1] for c in cells)
    nS = sum(c[2] for c in cells)
    kS = sum(c[3] for c in cells)
    out = {"strata": len(keys), "nWinter": nW, "nSummer": nS,
           "rawWinterPct": round(100.0 * kW / nW, 2) if nW else None,
           "rawSummerPct": round(100.0 * kS / nS, 2) if nS else None}
    if d_obs is None:
        out.update({"controlledDiffPt": None, "pTwoSided": None, "nullSdPt": None, "mdePt": None})
        return out, None
    null = np.zeros(s1.NPERM)
    for k in keys:
        nw, kw, ns, ks = strata[k]
        null += s1.null_draws(k, nw, ns, kw + ks)
    null = null / wsum
    p_two = (1.0 + float(np.sum(np.abs(null) >= abs(d_obs)))) / (s1.NPERM + 1.0)
    sd = float(np.std(null))
    out.update({"controlledDiffPt": round(100 * d_obs, 3), "pTwoSided": round(p_two, 6),
                "nullSdPt": round(100 * sd, 3), "mdePt": round(100 * 2.8 * sd, 3),
                "fillRatio": round(abs(d_obs) / (2.8 * sd), 2) if sd > 0 else None})
    return out, d_obs


def main():
    try:
        import numpy  # noqa: F401
    except ImportError:
        s1.stop("numpy が無い")
    if not os.path.exists(STAGE1):
        s1.stop("stage1.json が無い")
    with io.open(STAGE1, encoding="utf-8") as f:
        ref = json.load(f)["summary"]["main"]["controlledDiffPt"]
    strata, total = build_strata()
    if not (520000 <= total <= 570000):
        s1.stop("レース総数が想定外: %d" % total)
    keys = sorted(k for k, c in strata.items() if c[0] > 0 and c[2] > 0)
    overall, d_all = test_cells(strata, keys)
    if round(100 * d_all, 3) != ref:
        s1.stop("全体の差が stage1 と一致しない: %.3f / %.3f" % (100 * d_all, ref))
    by_c1 = {}
    for b in C1_BINS:
        ks = [k for k in keys if k.split("|")[3] == b]
        by_c1[b], _ = test_cells(strata, ks)
    by_out = {}
    for b in OUT_BINS:
        ks = [k for k in keys if k.split("|")[4] == b]
        by_out[b], _ = test_cells(strata, ks)
    summary = {
        "stage": 2, "seed": s1.SEED, "nperm": s1.NPERM, "races": total,
        "overall": overall,
        "byC1Strength": by_c1,
        "byOuterStrength": by_out,
        "notes": ["c1 strength = prior 12-month win rate of the course-1 racer; new = under 30 starts",
                  "outer strength = mean prior 12-month win rate of the other boats with 30+ starts",
                  "fillRatio = |diff| / (2.8 x null sd); under 1.0 means underpowered"],
    }
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "stage2.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"summary": summary}, f, ensure_ascii=False, indent=1)
    print("OK stage2 races=%d overall=%.3f" % (total, 100 * d_all))


if __name__ == "__main__":
    main()
