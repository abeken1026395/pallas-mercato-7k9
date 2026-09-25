# -*- coding: utf-8 -*-
# stage1.py … 検証04 宿題（場×レース番号）の本体
#
# 1. stage0 の年ごとの出力をまとめ、公開中の本文の値と突き合わせる（ゲート）。
#    1つでも外れたら何も書かずに止まる。
# 2. 場ごとの「山と谷の差」 S_v ＝ 10R から 12R の的中率 − 2R から 4R の的中率。
# 3. 入れ替えA：場×開催日ごとに谷と山を確率1/2で入れ替える（場ごとの形があるか）。
# 4. 入れ替えB：同じ年の中で場×開催日の単位を場のあいだで入れ替える（場で形が違うか）。
# 5. 判定は design.md のとおり。出力は CSV と summary.json（この フォルダ）。
import io
import os
import sys
import json
import numpy as np

PARTS = r"C:\Users\USER\kensho04parts"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_TALLY = os.path.join(HERE, "..", "..", "docs", "data", "ninkiTally.json")
YEARS = [str(y) for y in range(2016, 2027)]
SEED = 20260925
NPERM = 1000
EARLY = (2, 3, 4)
LATE = (10, 11, 12)

VENUE = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
    "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
    "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀",
    "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}
# 公開中の本文（docs/kensho/ninki/index.html）の表の値
PUB_VENUE = {"大村": "12.72", "徳山": "12.38", "芦屋": "11.42", "津": "11.37", "尼崎": "11.34",
             "下関": "11.29", "福岡": "11.24", "住之江": "10.89", "蒲郡": "10.76", "唐津": "10.70",
             "常滑": "10.62", "宮島": "10.61", "児島": "10.51", "丸亀": "10.41", "若松": "10.31",
             "びわこ": "10.29", "三国": "10.20", "桐生": "9.92", "浜名湖": "9.75", "多摩川": "9.72",
             "鳴門": "8.86", "江戸川": "8.11", "平和島": "7.88", "戸田": "7.78"}
# 本文のレース番号の図の点の縦位置（9%が131.1、1ポイント37.7）
PUB_RNO_Y = [71.6, 126.2, 138.7, 121.3, 75.7, 87.0, 68.2, 58.0, 83.6, 48.9, 28.9, 30.4]
MASK64 = (1 << 64) - 1


def splitmix64(*xs):
    z = 0
    for x in xs:
        z = (z + 0x9E3779B97F4A7C15 + int(x)) & MASK64
        y = z
        y = ((y ^ (y >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        y = ((y ^ (y >> 27)) * 0x94D049BB133111EB) & MASK64
        z = y ^ (y >> 31)
    return z


def season(hd):
    """9月始まりの1年（1..10）。2026-09-01 は10年目に入れる"""
    y, m = int(hd[:4]), int(hd[4:6])
    k = (y - 2016) + (1 if m >= 9 else 0)
    return min(k, 10)


def stop(msg):
    print("STOP:", msg)
    sys.exit(3)


def load():
    units = {}
    rows = 0
    kd = {}
    kn = {}
    days = 0
    for y in YEARS:
        with io.open(os.path.join(PARTS, "stage0_%s.json" % y), encoding="utf-8") as f:
            d = json.load(f)
        if d["badRno"]:
            stop("レース番号の読めない行 %d (%s)" % (d["badRno"], y))
        rows += d["rows"]
        days += d["days"]
        for k, v in d["exclKumiDash"].items():
            kd[k] = kd.get(k, 0) + v
        for k, v in d["exclNinki"].items():
            kn[k] = kn.get(k, 0) + v
        units.update(d["units"])
    return units, rows, days, kd, kn


def gates(units, rows, days, kd, kn):
    # 全体
    H = sum(u[r][0] for u in units.values() for r in range(1, 13))
    N = sum(u[r][1] for u in units.values() for r in range(1, 13))
    g = {"days": days, "rows": rows, "races": N, "hits": H,
         "exclKumiDash": kd, "exclNinki": kn}
    if days != 3653 or rows != 557172 or N != 534330 or H != 55562:
        stop("全体が合わない %r" % g)
    if kn != {"返": 15461}:
        stop("返の数が合わない %r" % kn)
    if kd.get("stop", 0) != 6866 or kd.get("1", 0) != 227 or kd.get("5", 0) != 209 \
            or kd.get("0", 0) != 79 or sum(kd.values()) != 7381:
        stop("除外の内訳が合わない %r" % kd)
    # 場ごと：リポジトリの ninkiTally.json と全件一致
    with io.open(REPO_TALLY, encoding="utf-8") as f:
        tally = json.load(f)["日別"]
    rep = {}
    for hd, dd in tally.items():
        for jcd, (h, n) in dd.items():
            a = rep.setdefault(jcd, [0, 0])
            a[0] += h
            a[1] += n
    mine = {}
    for key, u in units.items():
        hd, jcd = key.split("|")
        a = mine.setdefault(jcd, [0, 0])
        a[0] += sum(u[r][0] for r in range(1, 13))
        a[1] += sum(u[r][1] for r in range(1, 13))
        # 日別×場別も一致
        t = tally.get(hd, {}).get(jcd)
        if t is None or t[0] != sum(u[r][0] for r in range(1, 13)) \
                or t[1] != sum(u[r][1] for r in range(1, 13)):
            stop("日別×場別が ninkiTally.json と合わない %s %r %r" % (key, t, u))
    nunit_tally = sum(len(dd) for dd in tally.values())
    if nunit_tally != len(units):
        stop("場×開催日の数が合わない %d %d" % (nunit_tally, len(units)))
    if mine != rep:
        stop("場ごとの合計が ninkiTally.json と合わない")
    for jcd, (h, n) in mine.items():
        s = "%.2f" % (100.0 * h / n)
        if PUB_VENUE[VENUE[jcd]] != s:
            stop("場の的中率が本文と合わない %s %s %s" % (VENUE[jcd], s, PUB_VENUE[VENUE[jcd]]))
    # レース番号ごと
    rh = [0] * 13
    rn = [0] * 13
    for u in units.values():
        for r in range(1, 13):
            rh[r] += u[r][0]
            rn[r] += u[r][1]
    rrate = [None] + [100.0 * rh[r] / rn[r] for r in range(1, 13)]
    if "%.2f" % rrate[3] != "8.80" or "%.2f" % rrate[11] != "11.71":
        stop("3R・11R が本文と合わない %.4f %.4f" % (rrate[3], rrate[11]))
    maxdev = 0.0
    for r in range(1, 13):
        fig = 9 + (131.1 - PUB_RNO_Y[r - 1]) / 37.7
        maxdev = max(maxdev, abs(fig - rrate[r]))
    if maxdev > 0.01:
        stop("レース番号の図と合わない（最大のずれ %.4f）" % maxdev)
    if sum(rn[1:]) != N or sum(rh[1:]) != H:
        stop("レース番号の合計が全体と合わない")
    g["venueMatchesRepoTally"] = True
    g["venueRatesMatchPage"] = 24
    g["rnoFigureMaxDev"] = round(maxdev, 4)
    g["units"] = len(units)
    return g, mine, rh, rn


def arrays(units):
    keys = sorted(units)
    jcd = np.array([int(k.split("|")[1]) for k in keys])
    seas = np.array([season(k.split("|")[0]) for k in keys])
    hE = np.array([sum(units[k][r][0] for r in EARLY) for k in keys], dtype=np.int64)
    nE = np.array([sum(units[k][r][1] for r in EARLY) for k in keys], dtype=np.int64)
    hL = np.array([sum(units[k][r][0] for r in LATE) for k in keys], dtype=np.int64)
    nL = np.array([sum(units[k][r][1] for r in LATE) for k in keys], dtype=np.int64)
    return keys, jcd, seas, hE, nE, hL, nL


def svals(jcd, hE, nE, hL, nL):
    b = lambda x: np.bincount(jcd, weights=x, minlength=25)[1:]
    return 100.0 * (b(hL) / b(nL) - b(hE) / b(nE))


def permA(v, jcd, hE, nE, hL, nL):
    m = jcd == v
    a, b, c, d = hE[m], nE[m], hL[m], nL[m]
    rng = np.random.Generator(np.random.PCG64(splitmix64(SEED, v)))
    out = np.empty(NPERM)
    for i in range(NPERM):
        f = rng.random(a.size) < 0.5
        HE = np.where(f, c, a).sum(); NE = np.where(f, d, b).sum()
        HL = np.where(f, a, c).sum(); NL = np.where(f, b, d).sum()
        out[i] = 100.0 * (HL / NL - HE / NE)
    return out


def permB(jcd, seas, hE, nE, hL, nL, order):
    idx = {s: np.where(seas == s)[0] for s in range(1, 11)}
    D = np.empty(NPERM)
    for i in range(NPERM):
        sums = np.zeros((4, 25), dtype=np.int64)
        for s in order:
            ix = idx[s]
            rng = np.random.Generator(np.random.PCG64(splitmix64(SEED, s, i)))
            lab = jcd[ix][rng.permutation(ix.size)]
            for k, x in enumerate((hE, nE, hL, nL)):
                sums[k] += np.bincount(lab, weights=x[ix], minlength=25).astype(np.int64)
        S = 100.0 * (sums[2, 1:] / sums[3, 1:] - sums[0, 1:] / sums[1, 1:])
        D[i] = S.std()
    return D


def main():
    units, rows, days, kd, kn = load()
    g, mine, rh, rn = gates(units, rows, days, kd, kn)
    print("gates ok", json.dumps(g, ensure_ascii=False))

    keys, jcd, seas, hE, nE, hL, nL = arrays(units)
    S = svals(jcd, hE, nE, hL, nL)
    Snat = 100.0 * (hL.sum() / nL.sum() - hE.sum() / nE.sum())
    short = int(((nE == 0) | (nL == 0)).sum())

    # 入れ替えA（場ごと）。分割不変の自己照合：場を2つに分けて回した結果と全部まとめた結果
    nullA = {v: permA(v, jcd, hE, nE, hL, nL) for v in range(1, 25)}
    chk = {}
    for grp in (range(1, 13), range(13, 25)):
        for v in grp:
            chk[v] = permA(v, jcd, hE, nE, hL, nL)
    devA = max(float(np.abs(nullA[v] - chk[v]).max()) for v in range(1, 25))
    if devA > 1e-12:
        stop("入れ替えAが分割で変わる %g" % devA)

    # 入れ替えB（場で違うか）。年の順を逆にしても同じか
    Dobs = float(S.std())
    DB = permB(jcd, seas, hE, nE, hL, nL, list(range(1, 11)))
    DB2 = permB(jcd, seas, hE, nE, hL, nL, list(range(10, 0, -1)))
    devB = float(np.abs(DB - DB2).max())
    if devB > 1e-12:
        stop("入れ替えBが年の順で変わる %g" % devB)
    pB = float((DB >= Dobs).mean())

    # 全国の年ごとの S
    yS = []
    for s in range(1, 11):
        m = seas == s
        yS.append(100.0 * (hL[m].sum() / nL[m].sum() - hE[m].sum() / nE[m].sum()))

    rowsA = []
    for v in range(1, 25):
        sd = float(nullA[v].std())
        mdd = 2.8 * sd
        p = float((np.abs(nullA[v]) >= abs(S[v - 1])).mean())
        m = jcd == v
        rowsA.append({"code": "%02d" % v, "venue": VENUE["%02d" % v],
                      "early_hit": int(hE[m].sum()), "early_n": int(nE[m].sum()),
                      "late_hit": int(hL[m].sum()), "late_n": int(nL[m].sum()),
                      "early_rate": 100.0 * hE[m].sum() / nE[m].sum(),
                      "late_rate": 100.0 * hL[m].sum() / nL[m].sum(),
                      "S": float(S[v - 1]), "nullSD": sd, "minDiff": mdd,
                      "fill": float(S[v - 1]) / mdd, "p": p, "days": int(m.sum())})

    cond1 = all(r["S"] > 0 for r in rowsA)
    cond2 = pB >= 0.05
    verdict = "同じ形" if (cond1 and cond2) else ("向きは同じ、大きさは違う" if cond1 else "同じと言えない")

    # 出力
    with io.open(os.path.join(HERE, "venueShape.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("code,venue,days,early_hit,early_n,early_rate,late_hit,late_n,late_rate,S,nullSD,minDiff,fill,p\n")
        for r in sorted(rowsA, key=lambda r: -r["S"]):
            f.write("%s,%s,%d,%d,%d,%.4f,%d,%d,%.4f,%.4f,%.4f,%.4f,%.3f,%.3f\n"
                    % (r["code"], r["venue"], r["days"], r["early_hit"], r["early_n"], r["early_rate"],
                       r["late_hit"], r["late_n"], r["late_rate"], r["S"], r["nullSD"],
                       r["minDiff"], r["fill"], r["p"]))
    # 場×レース番号
    cell = {}
    for k, u in units.items():
        v = k.split("|")[1]
        for r in range(1, 13):
            c = cell.setdefault((v, r), [0, 0])
            c[0] += u[r][0]
            c[1] += u[r][1]
    with io.open(os.path.join(HERE, "venueRace.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("code,venue,race,hit,n,rate\n")
        for v in sorted(VENUE):
            for r in range(1, 13):
                h, n = cell[(v, r)]
                f.write("%s,%s,%d,%d,%d,%.4f\n" % (v, VENUE[v], r, h, n, 100.0 * h / n))
        for r in range(1, 13):
            f.write("00,全国,%d,%d,%d,%.4f\n" % (r, rh[r], rn[r], 100.0 * rh[r] / rn[r]))
    with io.open(os.path.join(HERE, "nullSpread.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("iter,D\n")
        for i, x in enumerate(DB):
            f.write("%d,%.6f\n" % (i, x))
    summ = {"gates": g, "Snational": Snat, "shortUnits": short,
            "Dobs": Dobs, "nullD_mean": float(DB.mean()), "nullD_p95": float(np.percentile(DB, 95)),
            "nullD_max": float(DB.max()), "pB": pB,
            "cond1_allPositive": cond1, "nPositive": sum(1 for r in rowsA if r["S"] > 0),
            "nFillGe1": sum(1 for r in rowsA if r["fill"] >= 1.0),
            "cond2_pB_ge_0.05": cond2, "verdict": verdict,
            "S_min": min(r["S"] for r in rowsA), "S_max": max(r["S"] for r in rowsA),
            "seasonS": yS, "seasonPositive": sum(1 for x in yS if x > 0),
            "selfCheck": {"permA_splitDev": devA, "permB_orderDev": devB},
            "seed": SEED, "nperm": NPERM}
    with io.open(os.path.join(HERE, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(summ, ensure_ascii=False, indent=1))
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
