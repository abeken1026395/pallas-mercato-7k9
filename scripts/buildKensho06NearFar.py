# -*- coding: utf-8 -*-
# buildKensho06NearFar.py
# 検証06 の追加分。buildKensho06Home.py（stage0〜8）の結果と中間ファイル analysis.npz をそのまま使い、
#   stage9   近接（同じ地区の他支部）が遠隔（別地区）より悪いのは本物か
#   stage7mc stage7 の場別24本・年別11本に多重比較の補正（判定列を足すだけ）
# を summary.json に追記する。stage0〜8 は再計算しない。既存のキーは書き換えない。
#
# 使い方:
#   py -3 scripts/buildKensho06NearFar.py stage9   <作業ディレクトリ>
#   py -3 scripts/buildKensho06NearFar.py stage7mc <作業ディレクトリ>
import os
import sys
import csv
import json
import math
import time
import collections

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildKensho06Home as H  # noqa: E402  関数と定数だけを使う（書き換えない）

OUTDIR = H.OUTDIR
DELTA9 = 0.01                 # stage9-5 で検出したい1着率の差（近接−遠隔の観測 .74pt に合わせて 1pt）
DISTRICTS = ["関東", "東海", "近畿", "四国", "中国", "九州"]


def tiers(D):
    """0 完全地元 / 1 近接 / 2 遠隔（stage6 と同じ定義）。vd は開催場の地区"""
    rd, vd = H.district_of(D)
    return np.where(D["home"], 0, np.where(rd == vd, 1, 2)).astype(np.int8), vd


def frozen_parts(s):
    """変えてはいけない部分（stage7 は既存キーだけ）"""
    keep = {k: v for k, v in s.items() if k not in ("stage7", "stage9")}
    if "stage7" in s:
        keep["stage7"] = {k: v for k, v in s["stage7"].items() if k != "multipleComparison"}
    return json.dumps(keep, ensure_ascii=False, sort_keys=True)


def save_checked(s, before):
    if frozen_parts(s) != before:
        print("STOP: 既存の stage0〜8 の値が変わった（保存しない）")
        sys.exit(1)
    H.save_summary(s)
    if frozen_parts(H.load_summary()) != before:
        print("STOP: 保存後に既存の値が変わっていた")
        sys.exit(1)


# ---------------------------------------------------------------- stage9-1

def stage9_1(D, T):
    ab = H.age_band(D)
    sb, q = H.starts_band(D)
    axes = [
        ("級別", D["rank"].astype(np.int64), [(i, r) for i, r in enumerate(H.RANKS)]),
        ("進入コース", D["course"].astype(np.int64), [(c, "%dコース" % c) for c in range(1, 7)] + [(0, "不明")]),
        ("場", D["jcd"].astype(np.int64), [(int(j), j + " " + H.VENUE_BRANCH[j][0]) for j in sorted(H.VENUE_BRANCH)]),
        ("年齢帯", ab.astype(np.int64), [(i, x[2]) for i, x in enumerate(H.AGE_BANDS)]),
        ("出走数帯", sb.astype(np.int64), [(0, "Q1（〜%g）" % q[0]), (1, "Q2（〜%g）" % q[1]),
                                          (2, "Q3（〜%g）" % q[2]), (3, "Q4（%g超）" % q[2])]),
    ]
    near, far = T == 1, T == 2
    nN, nF = int(near.sum()), int(far.sum())
    rows, tv = [], {}
    for name, v, levels in axes:
        ml = max(l for l, _ in levels) + 1
        cN = np.bincount(v[near], minlength=ml)
        cF = np.bincount(v[far], minlength=ml)
        d = 0.0
        for lv, label in levels:
            sN, sF = cN[lv] / nN, cF[lv] / nF
            d += abs(sN - sF) / 2
            rows.append({"axis": name, "level": label, "nNear": int(cN[lv]), "shareNear": round(sN, 6),
                         "nFar": int(cF[lv]), "shareFar": round(sF, 6), "diffNearMinusFar": round(sN - sF, 6)})
        tv[name] = round(d, 6)
    with open(os.path.join(OUTDIR, "nearFarStrata.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    top = sorted(rows, key=lambda r: -abs(r["diffNearMinusFar"]))[:10]
    return {
        "definition": "近接・遠隔それぞれの延べ走を分母にした構成比。軸ごとの違いの大きさは全変動距離（構成比の差の絶対値の和の半分。0〜1）",
        "nNear": nN, "nFar": nF,
        "startsQuartileCuts": [float(x) for x in q],
        "axisDistanceNearVsFar": dict(sorted(tv.items(), key=lambda x: -x[1])),
        "largestLevelDiffs": [{k: r[k] for k in ("axis", "level", "nNear", "shareNear", "nFar", "shareFar",
                                                 "diffNearMinusFar")} for r in top],
        "file": "analysis/kensho06/nearFarStrata.csv",
    }


# ---------------------------------------------------------------- stage9-2

def shuffle3(D, T, r0, r1):
    """stage2 と同じ乱数（splitmix64・(seed+レース通番, 枠内の位置, rep)）で、3値ラベルだけをレース内で並べ替える"""
    rid = D["rid"]
    fin = D["fin"]
    win = (fin == 1).astype(np.float64)
    top3 = (fin <= 3).astype(np.float64)
    fin64 = fin.astype(np.float64)
    with np.errstate(over="ignore"):
        base = H.splitmix(H.splitmix(np.uint64(H.SEED) + rid.astype(np.uint64)) ^ D["pos"].astype(np.uint64))
    ridf = rid.astype(np.float64)
    nr = int(rid.max()) + 1
    obsCnt = np.bincount(rid * 3 + T.astype(np.int64), minlength=nr * 3)
    R = r1 - r0
    out = {"sums": np.zeros((R, 3, 3)), "countOk": np.zeros(R, dtype=bool)}
    for i, rep in enumerate(range(r0, r1)):
        with np.errstate(over="ignore"):
            u = H.splitmix(base ^ np.uint64(H.splitmix_int(rep + 1)))
        key = ridf + (u >> np.uint64(11)).astype(np.float64) * (2.0 ** -53)
        order = np.argsort(key, kind="stable")
        lab = T[order].astype(np.int64)   # 行 k には、レース内で並べ替えた先の行のラベルが付く（stage2 と同じ向き）
        for j, arr in enumerate((win, top3, fin64)):
            out["sums"][i, j] = np.bincount(lab, weights=arr, minlength=3)
        out["countOk"][i] = np.array_equal(np.bincount(rid * 3 + lab, minlength=nr * 3), obsCnt)
    return out


def pair_diff(sums, n, a, b):
    return sums[..., a] / n[a] - sums[..., b] / n[b]


def stage9_2(D, T, work):
    t0 = time.time()
    full = shuffle3(D, T, 0, H.NREP)
    secs = round(time.time() - t0, 1)
    np.savez(os.path.join(work, "nullNearFar.npz"), **full)
    fin = D["fin"].astype(np.float64)
    n = np.bincount(T, minlength=3).astype(np.float64)
    obs = np.stack([np.bincount(T, weights=(fin == 1), minlength=3),
                    np.bincount(T, weights=(fin <= 3), minlength=3),
                    np.bincount(T, weights=fin, minlength=3)])
    res = {}
    for name, a, b in (("nearMinusFar", 1, 2), ("homeMinusNear", 0, 1)):
        res[name] = {}
        for j, (m, _) in enumerate(H.METRICS):
            res[name][m] = H.nullstat(pair_diff(obs[j], n, a, b), pair_diff(full["sums"][:, j, :], n, a, b))
    # stage2 と同じ乱数かの検算：完全地元ラベルの合計は stage2 の null.npz と一致するはず
    nz = np.load(os.path.join(work, "null.npz"))
    same = bool(np.allclose(full["sums"][:, :, 0], nz["all"], rtol=0, atol=1e-6))
    return {
        "definition": "同一レース内で「完全地元／近接／遠隔」の3値ラベルだけを並べ替える（%d回・seed %d・splitmix64、stage2 と同じ乱数）。"
                      "進入コース・着・級別は動かさない。p は帰無平均からの絶対偏差で数えた両側 (1+#)/(1+%d)" % (H.NREP, H.SEED, H.NREP),
        "controls": "レース内シャッフルは場・日・番組（同じレースの相手）を自動的に揃えるが、級別は統制しない"
                    "（同じレースの中に級別の違う選手がいて、ラベルと一緒に級別は動かないため）",
        "reps": H.NREP,
        "n": {"home": int(n[0]), "near": int(n[1]), "far": int(n[2])},
        "stats": res,
        "conservation": {"check": "レースごとの3値の個数（レース×ラベルの件数）が観測と完全一致した rep 数",
                         "repsMatched": int(full["countOk"].sum()), "reps": H.NREP,
                         "allRepsMatched": bool(full["countOk"].all())},
        "sameRandomAsStage2": {"check": "完全地元ラベルの1着・3着内・着の合計が、全repで stage2 の null.npz と一致するか",
                               "identical": same},
        "seconds": secs,
    }


# ---------------------------------------------------------------- stage9-3

def stage9_3(D, T):
    ab = H.age_band(D)
    sb, q = H.starts_band(D)
    fin = D["fin"].astype(np.float64)
    Y = np.stack([(fin == 1).astype(np.float64), (fin <= 3).astype(np.float64), fin], axis=1)
    P = 41
    acc = {}
    for y in H.YEARS:
        idx = np.flatnonzero(D["year"] == y)
        lo, hi = int(idx[0]), int(idx[-1]) + 1
        assert hi - lo == len(idx)
        a = {"XtX": np.zeros((P, P)), "Xty": np.zeros((P, 3)),
             "sx": np.zeros((3, P)), "sy": np.zeros((3, 3)), "n": np.zeros(3)}
        for st in range(lo, hi, 300000):
            sl = slice(st, min(st + 300000, hi))
            X40 = H.design(D, sl, ab, sb)
            t = T[sl]
            X = np.hstack([X40[:, :2], (t == 1).astype(np.float64)[:, None], X40[:, 2:]])
            a["XtX"] += X.T @ X
            a["Xty"] += X.T @ Y[sl]
            for g in range(3):
                mk = t == g
                a["sx"][g] += X[mk].sum(axis=0)
                a["sy"][g] += Y[sl][mk].sum(axis=0)
                a["n"][g] += mk.sum()
        acc[y] = a
    tot = {k: sum(a[k] for a in acc.values()) for k in acc[H.YEARS[0]]}
    # 列: 0 切片 / 1 完全地元 / 2 近接 / 3..25 場 / 26..28 級別 / 29..34 進入 / 35..37 年齢帯 / 38..40 出走数帯
    cols = {"venue": range(3, 26), "rank": range(26, 29), "course": range(29, 35),
            "age": range(35, 38), "starts": range(38, 41)}

    def fit(a, j):
        beta = np.linalg.lstsq(a["XtX"], a["Xty"][:, j], rcond=None)[0]
        mean = a["sx"] / a["n"][:, None]
        ym = a["sy"][:, j] / a["n"]
        raw = ym[1] - ym[2]
        parts = {f: float((mean[1] - mean[2])[list(c)] @ beta[list(c)]) for f, c in cols.items()}
        closure = raw - sum(parts.values()) - beta[2]
        return beta, ym, raw, parts, closure

    res, byYear = {}, {}
    for j, (m, _) in enumerate(H.METRICS):
        beta, ym, raw, parts, closure = fit(tot, j)
        res[m] = {
            "coefHome": round(float(beta[1]), 6), "coefNear": round(float(beta[2]), 6),
            "rawHomeMinusFar": round(float(ym[0] - ym[2]), 6), "rawNearMinusFar": round(float(raw), 6),
            "nearWorseThanFarAfterControl": bool(beta[2] < 0) if m != "meanFinish" else bool(beta[2] > 0),
            "nearWorseMeaning": "近接の係数が遠隔（基準0）より%s" % ("低い" if m != "meanFinish" else "大きい（平均着が悪い）"),
            "coefNearShareOfRaw": round(float(beta[2] / raw), 3),
            "nearMinusFarDecomposition": {H.FACTOR_JA[f]: round(v, 6) for f, v in parts.items()},
            "closureError": float(closure),
        }
        byYear[m] = {}
        for y, a in acc.items():
            b, _, r, _, _ = fit(a, j)
            byYear[m][str(y)] = {"coefHome": round(float(b[1]), 6), "coefNear": round(float(b[2]), 6),
                                 "rawNearMinusFar": round(float(r), 6)}
        signs = [np.sign(v["coefNear"]) for v in byYear[m].values()]
        res[m]["yearsCoefNearSameSignAsOverall"] = int(sum(1 for x in signs if x == np.sign(beta[2])))
        res[m]["years"] = len(signs)
    return {
        "definition": "stage3 と同じ線形確率モデル（1着・3着内）／線形モデル（平均着）。地元ダミーの代わりに完全地元ダミー・近接ダミー"
                      "（基準＝遠隔）を入れ、場(24)・級別(4)・進入コース(1〜6＋不明)・年齢帯(4)・出走数帯(4)で統制して全行に当てた。"
                      "近接−遠隔の統制前の差＝Σ(近接の平均−遠隔の平均)×係数＋近接ダミーの係数（closureError はその誤差）。"
                      "係数の区間は出さない（理論分布を使わないため）。年ごとの符号は年別に同じモデルを当てて数えた",
        "startsQuartileCuts": [float(x) for x in q],
        "overall": res,
        "byYear": byYear,
    }


# ---------------------------------------------------------------- stage9-4

def stage9_4(D, T):
    order = np.lexsort((D["dnum"], D["toban"]))
    tb, br, dn = D["toban"][order], D["bidx"][order], D["dnum"][order]
    t = T[order]
    fin = D["fin"][order].astype(np.float64)
    course = D["course"][order].astype(np.int64)
    win, top3 = (fin == 1).astype(np.float64), (fin <= 3).astype(np.float64)
    cAll = D["course"].astype(np.int64)
    fAll = D["fin"].astype(np.float64)
    cnt = np.bincount(cAll, minlength=7)
    eWin = np.bincount(cAll, weights=(fAll == 1), minlength=7) / np.maximum(cnt, 1)
    eTop3 = np.bincount(cAll, weights=(fAll <= 3), minlength=7) / np.maximum(cnt, 1)
    eFin = np.bincount(cAll, weights=fAll, minlength=7) / np.maximum(cnt, 1)
    new = np.ones(len(tb), dtype=bool)
    new[1:] = (tb[1:] != tb[:-1]) | (br[1:] != br[:-1])
    sid = np.cumsum(new) - 1
    ns = int(sid[-1] + 1)

    def bc(w, mask):
        return np.bincount(sid[mask], weights=w[mask], minlength=ns)

    one = np.ones(len(tb))
    agg = {}
    for side, mk in (("N", t == 1), ("F", t == 2)):
        agg["n" + side] = bc(one, mk)
        agg["win" + side] = bc(win, mk)
        agg["top3" + side] = bc(top3, mk)
        agg["fin" + side] = bc(fin, mk)
        agg["eWin" + side] = bc(eWin[course], mk)
        agg["eTop3" + side] = bc(eTop3[course], mk)
        agg["eFin" + side] = bc(eFin[course], mk)
    first = np.flatnonzero(new)
    last = np.r_[first[1:] - 1, len(tb) - 1]
    stTob, stBr = tb[first], br[first]
    stintNo = np.zeros(ns, dtype=np.int64)
    for i in range(1, ns):
        stintNo[i] = stintNo[i - 1] + 1 if stTob[i] == stTob[i - 1] else 0
    elig = (agg["nN"] >= 20) & (agg["nF"] >= 20)
    with np.errstate(divide="ignore", invalid="ignore"):
        d = {
            "winDiff": agg["winN"] / agg["nN"] - agg["winF"] / agg["nF"],
            "winDiffCourseAdj": (agg["winN"] - agg["eWinN"]) / agg["nN"] - (agg["winF"] - agg["eWinF"]) / agg["nF"],
            "top3Diff": agg["top3N"] / agg["nN"] - agg["top3F"] / agg["nF"],
            "top3DiffCourseAdj": (agg["top3N"] - agg["eTop3N"]) / agg["nN"] - (agg["top3F"] - agg["eTop3F"]) / agg["nF"],
            "meanFinishDiff": agg["finN"] / agg["nN"] - agg["finF"] / agg["nF"],
            "meanFinishDiffCourseAdj": (agg["finN"] - agg["eFinN"]) / agg["nN"] - (agg["finF"] - agg["eFinF"]) / agg["nF"],
        }
    with open(os.path.join(OUTDIR, "nearFarWithinRacer.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["toban", "stint", "branch", "firstDate", "lastDate", "nNear", "nFar",
                    "winsNear", "winsFar", "top3Near", "top3Far", "eligible"] + list(d.keys()))
        for i in range(ns):
            w.writerow([int(stTob[i]), int(stintNo[i]), H.BRANCH18[stBr[i]], H.ymd(dn[first[i]]), H.ymd(dn[last[i]]),
                        int(agg["nN"][i]), int(agg["nF"][i]), int(agg["winN"][i]), int(agg["winF"][i]),
                        int(agg["top3N"][i]), int(agg["top3F"][i]), int(elig[i])] +
                       [("%.6f" % d[k][i]) if elig[i] else "" for k in d])

    def summ(x):
        x = x[elig]
        return {"median": round(float(np.median(x)), 6), "q1": round(float(np.quantile(x, 0.25)), 6),
                "q3": round(float(np.quantile(x, 0.75)), 6), "positive": int((x > 0).sum()),
                "negative": int((x < 0).sum()), "zero": int((x == 0).sum())}

    racers = set(stTob.tolist())
    eligR = set(stTob[elig].tolist())
    reasons = collections.Counter()
    for i in np.flatnonzero(~elig):
        if agg["nN"][i] < 20 and agg["nF"][i] < 20:
            reasons["両方20走未満"] += 1
        elif agg["nN"][i] < 20:
            reasons["近接だけ20走未満"] += 1
        else:
            reasons["遠隔だけ20走未満"] += 1
    return {
        "definition": "stage4 と同じ単位（選手×支部の連続区間。支部が変わったら別単位）。近接・遠隔の両方に20走以上ある単位だけを対象。"
                      "差＝近接での値−遠隔での値（平均着は小さいほど良い）。コース統制版は、各走から期待値（全行の進入コース別の"
                      "1着率・3着内率・平均着）を引いた残差の平均の差",
        "units": ns, "racers": len(racers),
        "eligibleUnits": int(elig.sum()), "excludedUnits": int((~elig).sum()),
        "eligibleRacers": len(eligR), "excludedRacers": len(racers - eligR),
        "excludedUnitReasons": dict(reasons),
        "raw": {k: summ(d[k]) for k in ("winDiff", "top3Diff", "meanFinishDiff")},
        "courseAdjusted": {k: summ(d[k]) for k in ("winDiffCourseAdj", "top3DiffCourseAdj", "meanFinishDiffCourseAdj")},
        "note": "単位ごとの差は n=20 からで、単位ごとの率は n<300。集計（中央値・四分位・符号の人数）だけを結果として使う",
        "file": "analysis/kensho06/nearFarWithinRacer.csv",
    }


# ---------------------------------------------------------------- stage9-5

def required_n(h, p0, delta):
    p1 = p0 + delta
    pbar = h * p1 + (1 - h) * p0
    a = H.Z * math.sqrt(pbar * (1 - pbar) * (1 / h + 1 / (1 - h)))
    b = H.Z_BETA * math.sqrt(p1 * (1 - p1) / h + p0 * (1 - p0) / (1 - h))
    return (a + b) ** 2 / delta ** 2


def stage9_5(D, T, vd):
    win = D["fin"] == 1
    layers = [("全体", np.ones(len(T), dtype=bool))]
    for i, dname in enumerate(DISTRICTS):
        layers.append((dname, vd == i))
    rows = []
    for key, m in layers:
        nN = int((m & (T == 1)).sum())
        nF = int((m & (T == 2)).sum())
        nT = nN + nF
        row = {"layer": key, "nNear": nN, "nFar": nF, "nTotal": nT}
        if nN == 0 or nF == 0:
            row.update({"nearShare": None, "p0FarWin": None, "requiredN": None, "sufficiency": None,
                        "note": "近接または遠隔が0で算出不可"})
        else:
            h = nN / nT
            p0 = float(win[m & (T == 2)].mean())
            req = required_n(h, p0, DELTA9)
            row.update({"nearShare": round(h, 6), "p0FarWin": round(p0, 6), "requiredN": int(math.ceil(req)),
                        "sufficiency": round(nT / req, 4), "note": "" if nT >= req else "充足率1.0未満"})
        rows.append(row)
    return {
        "definition": "α=0.05（両側）・検出力0.8。1着率で遠隔 p0（その層の実測）に対し近接が p0+0.01 のとき、近接比率 h（その層の実測）"
                      "のもとで2標本の比率の差を検出するのに要る延べ走数（近接＋遠隔）。stage5 と同じ式で差だけ 0.01。"
                      "地区の層は開催場の地区で切った（近接は選手の地区＝開催場の地区、遠隔はそれ以外の地区の選手）。"
                      "充足率1.0未満の層は順位も大小関係も書かない",
        "alpha": 0.05, "power": 0.8, "delta": DELTA9,
        "layers": rows,
        "underpoweredLayers": [r["layer"] for r in rows if r["note"]],
    }


def stage9(work):
    D = H.load(work)
    s = H.load_summary()
    before = frozen_parts(s)
    T, vd = tiers(D)
    st6 = s["stage6"]
    if int((T == 0).sum()) != st6["tier1Home"]["n"] or int((T == 1).sum()) != st6["tier2Near"]["n"] \
            or int((T == 2).sum()) != st6["tier3Far"]["n"]:
        print("STOP: 3値の件数が stage6 と一致しない")
        sys.exit(1)
    out = {"script": "scripts/buildKensho06NearFar.py", "python": sys.version.split()[0], "numpy": np.__version__,
           "runStartedJST": H.jst_now(),
           "input": "作業ディレクトリの analysis.npz と null.npz（stage0〜8 の中間物をそのまま使用。再解凍・再計算なし）",
           "tierDefinition": "stage6 と同じ（1 完全地元 / 2 近接＝同じ地区の他支部 / 3 遠隔＝別地区。地区は stage6.districtTable）"}
    out["stage9_1"] = stage9_1(D, T)
    print("9-1 done", H.jst_now(), flush=True)
    out["stage9_2"] = stage9_2(D, T, work)
    print("9-2 done", H.jst_now(), flush=True)
    out["stage9_3"] = stage9_3(D, T)
    print("9-3 done", H.jst_now(), flush=True)
    out["stage9_4"] = stage9_4(D, T)
    print("9-4 done", H.jst_now(), flush=True)
    out["stage9_5"] = stage9_5(D, T, vd)
    out["runFinishedJST"] = H.jst_now()
    stops = []
    if not out["stage9_2"]["conservation"]["allRepsMatched"]:
        stops.append("stage9-2 のレースごとの3値の個数が観測と一致しない rep があった")
    if out["stage9_5"]["layers"][0]["note"]:
        stops.append("stage9-5 の充足率が全体で1.0を下回った")
    if stops:
        out["stopped"] = stops
    s["stage9"] = out
    save_checked(s, before)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if stops:
        print("STOP:", stops)
        sys.exit(1)


# ---------------------------------------------------------------- stage7 多重比較

def bh(ps, q=0.05):
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    kmax = 0
    for rank, i in enumerate(order, 1):
        if ps[i] <= rank / m * q + 1e-12:
            kmax = rank
    rej = [False] * m
    for rank, i in enumerate(order, 1):
        rej[i] = rank <= kmax
    return rej, kmax


def correct(group):
    keys = [k for k, r in group.items() if isinstance(r["winWithinRaceNull"], dict)]
    ps = [group[k]["winWithinRaceNull"]["p"] for k in keys]
    m = len(ps)
    thr = 0.05 / m
    rej, kmax = bh(ps)
    rows, changed = {}, []
    for k, p, r in zip(keys, ps, rej):
        raw = p <= 0.05
        bon = p <= thr + 1e-12
        rows[k] = {"p": p, "significantRaw05": raw, "significantBonferroni": bon, "significantBH05": r}
        if raw != bon or raw != r:
            changed.append({"key": k, "p": p, "raw": raw, "bonferroni": bon, "bh": r})
    return {"tests": m, "bonferroniThreshold": thr, "bhMaxRank": kmax,
            "bhThresholdAtMaxRank": (kmax / m * 0.05) if kmax else None,
            "notTested": [k for k in group if k not in keys],
            "rows": rows, "judgementChanged": changed}


def stage7mc(work):
    s = H.load_summary()
    before = frozen_parts(s)
    s["stage7"]["multipleComparison"] = {
        "definition": "stage7 の winWithinRaceNull.p（レース内シャッフル1000回の両側p。下限 1/1001）に判定列を足す。既存の値・順位は変えない。"
                      "生の判定は p≤0.05、Bonferroni は p≤0.05/検定数、Benjamini-Hochberg は FDR 0.05（p を昇順に並べ、"
                      "p(k)≤k/検定数×0.05 を満たす最大の k までを有意）",
        "byVenue": correct(s["stage7"]["byVenue"]),
        "byYear": correct(s["stage7"]["byYear"]),
        "pResolutionNote": "シャッフル1000回の p は 1/1001 刻みで、下限 0.000999。下限に並んだものどうしには順位の意味がない（stage8）",
    }
    save_checked(s, before)
    print(json.dumps(s["stage7"]["multipleComparison"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # Windows の既定 cp932 では「≤」などが出せない
    cmd, work = sys.argv[1], sys.argv[2]
    {"stage9": stage9, "stage7mc": stage7mc}[cmd](work)
