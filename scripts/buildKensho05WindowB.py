# -*- coding: utf-8 -*-
# buildKensho05WindowB.py
# 検証05 段階14：窓B（2017-10-25〜2026-09-01）で本体の主要結果を回し直し、
# 分母A（10年・payrank 534,330行）と分母B（409日・results 2025-07-15〜）の既存値と並べる。
#
# 手順は buildKensho05Flow.py と同一（中心化・ペア定義・統計量・帰無A/B・1,000回・seed）。
# 部品は buildKensho05Flow.py から import し、段階ごとの式はそのまま写す。
# 写しが同一であることは --window A で既存の summary.json / CSV と突き合わせて確かめる。
#
# 入力（すべて読み取りのみ）
#   payrank/json                          払戻（採用の判定は Flow の load と同一）
#   C:\Users\USER\boatraceResults\json    v2 から取り直した結果（〜2025-07-14）
#   results/                              既存の結果（2025-07-15〜）
#
# 乱数：各パートは default_rng(20260914) から始め、置換は Flow と同じく
#   perm = argsort(系列番号 + rng.random(n)) を1回ずつ引く。1回あたりの乱数消費は n 個で
#   どの統計量を計算するかに依存しないので、パートを分けて別プロセスで回しても置換は同一。
#
# 使い方
#   py -3 scripts/buildKensho05WindowB.py run   --window A|B --part flow|cond|dec|course1
#   py -3 scripts/buildKensho05WindowB.py check                （窓A の4パートを既存出力と照合）
#   py -3 scripts/buildKensho05WindowB.py write                （窓B の4パートから stage14 と CSV を書く）
import os
import sys
import csv
import json
import math
import argparse
import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildKensho05Flow as K  # noqa: E402

V2_DIR = r"C:\Users\USER\boatraceResults\json"
V2_TO = "20250714"
WIN_B = ("20171025", "20260901")
WORKDIR = os.path.join(os.environ.get("TEMP", K.OUTDIR), "kensho05WindowB")
PARTS = ("flow", "cond", "dec", "course1")


# ---------------------------------------------------------------- 入力
def load_rows(window):
    cnt, rows, vdays = K.load(K.INDIR)
    K.assert_stage0(cnt)
    if window == "A":
        return rows, vdays
    lo, hi = WIN_B
    return ([t for t in rows if lo <= t[0] <= hi],
            {x for x in vdays if lo <= x[0] <= hi})


def results_dirs(window):
    """(ディレクトリ, 上限日) の並び。窓B は v2 取得分と既存 results を日付で分けて足す。"""
    if window == "A":
        return [(K.RESULTS_DIR, K.RESULTS_TO)]
    return [(V2_DIR, V2_TO), (K.RESULTS_DIR, WIN_B[1])]


def merge_maps(maps):
    out = {}
    for m in maps:
        dup = set(out) & set(m)
        if dup:
            K.stop("results の突合キーが2つの入力で重複: %s" % sorted(dup)[:3])
        out.update(m)
    return out


def load_res(window):
    parts = [K.load_results(d, to) for d, to in results_dirs(window)]
    files = (min(p[1][0] for p in parts), max(p[1][1] for p in parts))
    return merge_maps([p[0] for p in parts]), files


def load_dec(window):
    return merge_maps([K.load_results_decision(d, to) for d, to in results_dirs(window)])


def load_cond(window):
    parts = [K.load_results_conditions(d, to) for d, to in results_dirs(window)]
    keys = {"pre": {}, "post": {}}
    races = {"pre": 0, "post": 0}
    for _, kk, rr in parts:
        for per in keys:
            races[per] += rr[per]
            for k, v in kk[per].items():
                keys[per][k] = keys[per].get(k, 0) + v
    return merge_maps([p[0] for p in parts]), keys, races


# ---------------------------------------------------------------- 段階1〜8・10 の観測（Flow main と同一）
class Base(object):
    pass


def build_base(rows, vdays):
    b = Base()
    rows = sorted(rows, key=lambda t: (t[0], t[1], t[2]))
    n = len(rows)
    venues = sorted({t[1] for t in rows})
    vidx = {v: i for i, v in enumerate(venues)}
    ven = np.fromiter((vidx[t[1]] for t in rows), dtype=np.int64, count=n)
    rno = np.fromiter((t[2] for t in rows), dtype=np.int64, count=n)
    pay = np.fromiter((t[3] for t in rows), dtype=np.int64, count=n)
    skey = [(t[0], t[1]) for t in rows]
    sid = np.zeros(n, dtype=np.int64)
    for i in range(1, n):
        sid[i] = sid[i - 1] + (skey[i] != skey[i - 1])
    del skey
    if rno.min() < 1 or rno.max() > 12:
        K.stop("R が 1..12 の外にある")
    same = sid[1:] == sid[:-1]
    if np.any(same & (rno[1:] == rno[:-1])):
        K.stop("同一系列に同じRが複数ある（重複行）")

    # 段階1（五分位の境界はこの行集合の中で引く）
    yA = (pay >= K.MAN).astype(np.int64)
    srt = np.sort(pay)
    bounds = [int(srt[int(np.ceil(k * n / K.NQ)) - 1]) for k in range(1, K.NQ)]
    q = np.searchsorted(np.array(bounds), pay, side="left").astype(np.int64) + 1

    # 段階2（R差1のペア。Flow の d=1 と同じ並び）
    nseries = int(sid[-1]) + 1
    slen = np.bincount(sid)
    breaks = int((same & (rno[1:] - rno[:-1] >= 2)).sum())
    i = np.arange(n - 1)
    m = (sid[i + 1] == sid[i]) & (rno[i + 1] - rno[i] == 1)
    a1, b1 = i[m], i[m] + 1

    # 段階3・6b
    cell = ven * 12 + (rno - 1)
    ncell = np.bincount(cell, minlength=len(venues) * 12)
    mcell = np.bincount(cell, weights=yA, minlength=len(venues) * 12)
    if len(venues) != 24 or int((ncell > 0).sum()) != 288:
        K.stop("(場,R)セルが288にならない: 場%d / 非空セル%d"
               % (len(venues), int((ncell > 0).sum())))
    pcell = mcell / ncell
    pven = (np.bincount(ven, weights=yA) / np.bincount(ven))
    yf = yA.astype(float)
    zV = yf - pven[ven]
    e = yf - pcell[cell]
    qf = q.astype(float)
    mqcell = np.bincount(cell, weights=qf, minlength=len(venues) * 12) / ncell
    mqven = np.bincount(ven, weights=qf) / np.bincount(ven)
    zVq = qf - mqven[ven]
    eq = qf - mqcell[cell]

    # 段階7
    setsu, setsu_lens = K.build_setsu(vdays)
    starts = np.flatnonzero(np.r_[True, sid[1:] != sid[:-1]])
    s_day = np.empty(nseries, dtype=np.int64)
    s_len = np.empty(nseries, dtype=np.int64)
    for s, i0 in enumerate(starts):
        key = (rows[i0][0], rows[i0][1])
        if key not in setsu:
            K.stop("系列が節に割り当てられない: %s" % (key,))
        s_day[s], s_len[s] = setsu[key]
    s_last = s_day == s_len
    s_pen = s_day == s_len - 1
    la = s_last[sid[a1]]
    pa = s_pen[sid[a1]]
    m3 = ~(la | pa) & (rno[a1] < 10) & (rno[b1] < 10)
    a3, b3 = a1[m3], b1[m3]

    # 段階8 S3-D1
    Rc = rno.astype(float) - 6.5
    dprep = K.detrend_prep(sid, Rc, slen, 1)
    keep_s = dprep[2]
    m8 = keep_s[sid[a3]]
    c8 = dict(pairs=(a3[m8], b3[m8]), exSeries=int((~keep_s).sum()),
              exSeriesInSet=int(np.unique(sid[a3[~m8]]).size), exPairs=int((~m8).sum()))
    res1 = K.detrend(eq, sid, nseries, *dprep)
    if K.detrend_check(res1, sid, nseries, *dprep) > 1e-8:
        K.stop("残差化の直交性が崩れている: D1")

    # 段階10
    seg_start = np.r_[True, (sid[1:] != sid[:-1]) | (rno[1:] - rno[:-1] != 1)]

    for k, v in list(locals().items()):
        if k != "b":
            setattr(b, k, v)
    return b


# ---------------------------------------------------------------- 段階9・13 の突合（Flow main と同一）
def build_match(b, window):
    mt = Base()
    n, rows = b.n, b.rows
    resmap, res_files = load_res(window)
    with open(K.BEARING_PATH, encoding="utf-8") as f:
        bj = json.load(f)["場"]
    bearing = {j: float(v["方位"]) for j, v in bj.items()}
    have = np.zeros(n, dtype=bool)
    wmiss = np.zeros(n, dtype=bool)
    wsp = np.full(n, np.nan)
    wcode = np.zeros(n, dtype=np.int64)
    months = np.array([t[0][:6] for t in rows])
    for i, t in enumerate(rows):
        v = resmap.get((t[0], t[1], t[2]))
        if v is None:
            continue
        have[i] = True
        ms, code = v
        if K.is_int(ms) and K.is_int(code) and 1 <= code <= 17:
            wsp[i] = ms
            wcode[i] = code
        else:
            wmiss[i] = True
    excluded_months = []
    for mo in sorted(set(months[have].tolist())):
        mm = months == mo
        nm = int((have & mm).sum())
        if int((wmiss & mm).sum()) / nm > K.MISSING_MONTH_MAX:
            excluded_months.append(mo)
    M = have & ~wmiss & ~np.isin(months, excluded_months)
    Midx = np.flatnonzero(M)
    mW = M[b.a1] & M[b.b1]
    aW, bW = b.a1[mW], b.b1[mW]

    ang = np.where(M & (wcode >= 1) & (wcode <= 16),
                   np.deg2rad((wcode - 1) * 22.5), np.nan)
    comp = np.full(n, np.nan)
    for i in Midx:
        c = K.water_component(bearing[rows[i][1]], int(wcode[i]))
        if c is not None:
            comp[i] = c
    lvl = np.array(["無風" if wcode[i] == 17 else
                    {1: "追い風", 0: "横風", -1: "向かい風"}[int(comp[i])]
                    for i in Midx])
    spd = wsp[Midx]
    ym = b.eq[Midx]
    one = np.ones(len(Midx))
    d_oi = (lvl == "追い風").astype(float)
    d_mu = (lvl == "向かい風").astype(float)
    d_nw = (lvl == "無風").astype(float)
    Xb3 = np.column_stack([one, d_oi, d_mu, d_nw, spd, spd * d_oi, spd * d_mu])

    # 段階13 作業1
    condmap, ckeys, cnr = load_cond(window)
    cval = {c: np.full(n, np.nan) for c in K.COND_ITEMS}
    cmiss = {c: np.zeros(n, dtype=bool) for c in K.COND_ITEMS}
    for i in np.flatnonzero(have):
        v = condmap.get(rows[i][:3])
        if v is None:
            K.stop("段階13: 突合済みのレースが results に無い: %s" % (rows[i][:3],))
        for c, x in zip(K.COND_ITEMS, v):
            if K.cond_valid(c, x):
                cval[c][i] = x
            else:
                cmiss[c][i] = True
    ex13 = {c: [] for c in K.COND_ITEMS}
    for mo in sorted(set(months[have].tolist())):
        mm = have & (months == mo)
        nm = int(mm.sum())
        for c in K.COND_ITEMS:
            if int((cmiss[c] & mm).sum()) / nm > K.MISSING_MONTH_MAX:
                ex13[c].append(mo)
    M13 = M.copy()
    for c in K.COND_ITEMS:
        M13 &= ~cmiss[c] & ~np.isin(months, ex13[c])
    if not np.array_equal(M13, M):
        K.stop("段階13: 6項目の欠測・除外月で行集合が段階9と変わる（%d → %d）"
               % (M.sum(), M13.sum()))

    for k, v in list(locals().items()):
        if k not in ("mt", "b"):
            setattr(mt, k, v)
    return mt


def cell_center(b, x):
    ok = ~np.isnan(x)
    s = np.bincount(b.cell[ok], weights=x[ok], minlength=len(b.ncell))
    c = np.bincount(b.cell[ok], minlength=len(b.ncell))
    m = np.divide(s, c, out=np.zeros_like(s), where=c > 0)
    return x - m[b.cell]


# ---------------------------------------------------------------- パート
def part_flow(b):
    n, sidf = b.n, b.sid.astype(float)
    a1, b1 = b.a1, b.b1
    T1 = K.pearson(b.yf[a1], b.yf[b1])
    T2 = K.pearson(b.zV[a1], b.zV[b1])
    T3 = K.pearson(b.e[a1], b.e[b1])
    T1q = K.pearson(b.qf[a1], b.qf[b1])
    T2q = K.pearson(b.zVq[a1], b.zVq[b1])
    T3q = K.pearson(b.eq[a1], b.eq[b1])
    T3qS3 = K.pearson(b.eq[b.a3], b.eq[b.b3])
    pa8, pb8 = b.c8["pairs"]
    T8 = K.pearson(b.res1[pa8], b.res1[pb8])
    yH = b.yA.astype(bool)
    yL = b.q == 1
    hH_obs = K.runhist(yH, b.seg_start)
    hL_obs = K.runhist(yL, b.seg_start)
    s_obs = np.bincount(b.sid[a1], weights=b.eq[a1] * b.eq[b1], minlength=b.nseries)

    rng = np.random.default_rng(K.SEED)
    nullA = np.empty(K.NREP)
    nullAeq = np.empty(K.NREP)
    nullAS3 = np.empty(K.NREP)
    nullA8 = np.empty(K.NREP)
    nullH = np.empty((K.NREP, 13))
    nullL = np.empty((K.NREP, 13))
    s_ge = np.zeros(b.nseries, dtype=np.int64)
    for k in range(K.NREP):
        perm = np.argsort(sidf + rng.random(n))
        ep = b.e[perm]
        qp = b.q[perm]
        eqp = b.eq[perm]
        nullA[k] = K.pearson(ep[a1], ep[b1])
        nullAeq[k] = K.pearson(eqp[a1], eqp[b1])
        nullAS3[k] = K.pearson(eqp[b.a3], eqp[b.b3])
        r1 = K.detrend(eqp, b.sid, b.nseries, *b.dprep)
        nullA8[k] = K.pearson(r1[pa8], r1[pb8])
        nullH[k] = K.runhist(yH[perm], b.seg_start)
        nullL[k] = K.runhist(qp == 1, b.seg_start)
        sk = np.bincount(b.sid[a1], weights=eqp[a1] * eqp[b1], minlength=b.nseries)
        s_ge += sk >= s_obs - 1e-12
        if (k + 1) % 100 == 0:
            print("flow 帰無A %d/%d" % (k + 1, K.NREP), flush=True)
    rng = np.random.default_rng(K.SEED)
    cellf = b.cell.astype(float)
    base = np.argsort(b.cell, kind="stable")
    nullB = np.empty(K.NREP)
    nullBeq = np.empty(K.NREP)
    yp = np.empty(n)
    qp = np.empty(n, dtype=np.int64)
    for k in range(K.NREP):
        perm = np.argsort(cellf + rng.random(n))
        yp[base] = b.yf[perm]
        qp[base] = b.q[perm]
        ep = yp - b.pcell[b.cell]
        nullB[k] = K.pearson(ep[a1], ep[b1])
        eqp = qp - b.mqcell[b.cell]
        nullBeq[k] = K.pearson(eqp[a1], eqp[b1])
        if (k + 1) % 100 == 0:
            print("flow 帰無B %d/%d" % (k + 1, K.NREP), flush=True)

    dA = K.describe(nullA, T3)
    T4 = T3 - dA["mean"]
    dAeq = K.describe(nullAeq, T3q)
    T4q = T3q - dAeq["mean"]
    dS3 = K.describe(nullAS3, T3qS3)
    d8 = K.describe(nullA8, T8)

    def streak_table(h_obs, h_null):
        out = {}
        cols = [(str(k), h_obs[k], h_null[:, k]) for k in range(2, 7)]
        cols.append(("7+", h_obs[7:].sum(), h_null[:, 7:].sum(axis=1)))
        for label, ob, nu in cols:
            dsc = K.describe(nu.astype(float), float(ob))
            out[label] = {"observed": int(ob), "nullMean": dsc["mean"],
                          "nullSd": dsc["sd"], "p2_5": dsc["p2_5"],
                          "p97_5": dsc["p97_5"],
                          "ratio": float(ob) / dsc["mean"] if dsc["mean"] > 0 else None,
                          "pTwoSided": dsc["pTwoSided"]}
        return out
    p_series = (1 + s_ge) / (1 + K.NREP)
    tr = np.zeros((K.NQ, K.NQ), dtype=np.int64)
    np.add.at(tr, (b.q[a1] - 1, b.q[b1] - 1), 1)
    trans = {}
    for i, lab in ((0, "lowestToLowest"), (2, "middleToMiddle"), (4, "highestToHighest")):
        rs = int(tr[i].sum())
        trans[lab] = {"from": i + 1, "to": i + 1, "n": int(tr[i, i]), "rowTotal": rs,
                      "rowPct": float(100.0 * tr[i, i] / rs)}
    return {
        "stage1": {"manRate": float(b.yA.mean()), "manCount": int(b.yA.sum()), "n": b.n,
                   "quintileBounds": b.bounds},
        "stage2": {"series": b.nseries, "adjacentPairs": int(len(a1)), "breaks": b.breaks},
        "stage3": {"T1_raw": T1, "T2_venueCentered": T2, "T3_cellCentered": T3,
                   "T4_net": T4,
                   "decomposition": {"venueDiff_T1minusT2": T1 - T2,
                                     "rShape_T2minusT3": T2 - T3,
                                     "dayCommon_T3minusT4": T3 - T4},
                   "nullA": dA, "nullB": K.describe(nullB, T3)},
        "stage6b": {"T1q_raw": T1q, "T2q_venue": T2q, "T3q_cell": T3q, "T4q_net": T4q,
                    "decomposition": {"venueDiff_T1qminusT2q": T1q - T2q,
                                      "rShape_T2qminusT3q": T2q - T3q,
                                      "dayCommon_T3qminusT4q": T3q - T4q},
                    "nullA_eq": dAeq, "nullB_q": K.describe(nullBeq, T3q)},
        "stage7S3": {"nPairs": int(len(b.a3)), "T3q_cell": T3qS3, "nullA_eq": dS3,
                     "T4q_net": T3qS3 - dS3["mean"], "pTwoSided": dS3["pTwoSided"]},
        "stage8S3D1": {"pairSet": "S3", "detrend": "D1", "nPairs": int(len(pa8)),
                       "excludedSeries": b.c8["exSeries"],
                       "excludedSeriesInPairSet": b.c8["exSeriesInSet"],
                       "excludedPairs": b.c8["exPairs"], "T3q": T8, "nullA_eq": d8,
                       "net": T8 - d8["mean"], "pTwoSided": d8["pTwoSided"]},
        "stage10": {"segments": int(b.seg_start.sum()),
                    "H": streak_table(hH_obs, nullH), "L": streak_table(hL_obs, nullL),
                    "nSeries": b.nseries, "nBelow05": int((p_series < 0.05).sum()),
                    "shareBelow05": float((p_series < 0.05).mean())},
        "transitionS0": trans,
        "transitionMatrix": tr.tolist(),
    }


def part_cond(b, window):
    mt = build_match(b, window)
    n, M, Midx, aW, bW = b.n, mt.M, mt.Midx, mt.aW, mt.bW
    wvars = {"speed": np.where(M, mt.wsp, np.nan), "sin": np.sin(mt.ang),
             "cos": np.cos(mt.ang), "component": mt.comp}
    a9 = {}
    for name, x in wvars.items():
        xc = cell_center(b, x)
        ok = ~np.isnan(xc[aW]) & ~np.isnan(xc[bW])
        a9[name] = {"r": K.pearson(xc[aW][ok], xc[bW][ok]), "nPairs": int(ok.sum())}
    ym, one, spd = mt.ym, mt.one, mt.spd
    Pb3 = np.linalg.inv(mt.Xb3.T @ mt.Xb3) @ mt.Xb3.T
    rW1 = np.zeros(n)
    rW1[Midx] = ym - mt.Xb3 @ (Pb3 @ ym)
    TW0 = K.pearson(b.eq[aW], b.eq[bW])
    TW1 = K.pearson(rW1[aW], rW1[bW])

    cval = mt.cval
    wth = cval["天候コード"][Midx].astype(np.int64)
    wlev = sorted(set(wth.tolist()))
    if 1 not in wlev:
        K.stop("段階13: 天候コード1（晴）が無く基準水準が取れない")
    wdum = [(lv, (wth == lv).astype(float)) for lv in wlev if lv != 1]
    nw13 = mt.wcode[Midx] == 17
    sn13 = np.where(nw13, 0.0, np.sin(np.nan_to_num(mt.ang[Midx])))
    cn13 = np.where(nw13, 0.0, np.cos(np.nan_to_num(mt.ang[Midx])))
    allr = np.ones(len(Midx), dtype=bool)
    idefs = [
        ("風速", allr, np.column_stack([one, spd])),
        ("風向コード:角度", ~nw13, np.column_stack([one, sn13, cn13])),
        ("風向コード:水面成分", allr, np.column_stack([one, mt.d_oi, mt.d_mu, mt.d_nw])),
        ("波高", allr, np.column_stack([one, cval["波高"][Midx]])),
        ("気温", allr, np.column_stack([one, cval["気温"][Midx]])),
        ("水温", allr, np.column_stack([one, cval["水温"][Midx]])),
        ("天候コード", allr, np.column_stack([one] + [x for _, x in wdum])),
    ]
    item13 = {}
    for name, rm, X in idefs:
        beta, se, r2, nb = K.ols(X[rm], ym[rm])
        fit = np.full(n, np.nan)
        fit[Midx[rm]] = X[rm] @ beta
        fc = cell_center(b, fit)
        ok = ~np.isnan(fc[aW]) & ~np.isnan(fc[bW])
        a = K.pearson(fc[aW][ok], fc[bW][ok])
        item13[name] = {"a": a, "aPairs": int(ok.sum()), "b2_R2": r2, "n": nb,
                        "upper": a * r2}
    X7 = np.column_stack([one, spd, mt.d_oi, mt.d_mu, mt.d_nw, spd * mt.d_oi,
                          spd * mt.d_mu, sn13, cn13, cval["波高"][Midx],
                          cval["気温"][Midx], cval["水温"][Midx]] + [x for _, x in wdum])
    beta7, se7, r2_7, n7 = K.ols(X7, ym)
    P7 = np.linalg.inv(X7.T @ X7) @ X7.T
    rW7 = np.zeros(n)
    rW7[Midx] = ym - X7 @ (P7 @ ym)
    TW7 = K.pearson(rW7[aW], rW7[bW])

    rng = np.random.default_rng(K.SEED)
    sidf = b.sid.astype(float)
    nullW0 = np.empty(K.NREP)
    nullW1 = np.empty(K.NREP)
    nullW7 = np.empty(K.NREP)
    buf1 = np.zeros(n)
    buf7 = np.zeros(n)
    for k in range(K.NREP):
        perm = np.argsort(sidf + rng.random(n))
        eqp = b.eq[perm]
        nullW0[k] = K.pearson(eqp[aW], eqp[bW])
        yk = eqp[Midx]
        buf1[Midx] = yk - mt.Xb3 @ (Pb3 @ yk)
        nullW1[k] = K.pearson(buf1[aW], buf1[bW])
        buf7[Midx] = yk - X7 @ (P7 @ yk)
        nullW7[k] = K.pearson(buf7[aW], buf7[bW])
        if (k + 1) % 100 == 0:
            print("cond 帰無A %d/%d" % (k + 1, K.NREP), flush=True)
    W = {}
    for wname, obs, nul in (("W0", TW0, nullW0), ("W1", TW1, nullW1), ("W7", TW7, nullW7)):
        dW = K.describe(nul, obs)
        W[wname] = {"nPairs": int(len(aW)), "T3q": obs, "nullA_eq": dW,
                    "net": obs - dW["mean"], "pTwoSided": dW["pTwoSided"],
                    "insideNull95": bool(dW["p2_5"] <= obs <= dW["p97_5"])}
    return {
        "match": {"resultsFiles": {"from": mt.res_files[0], "to": mt.res_files[1]},
                  "excludedMonths": mt.excluded_months, "excludedMonths13": mt.ex13,
                  "matchedBeforeMonthExclusion": int(mt.have.sum()),
                  "matchedRaces": int(M.sum()), "adjacentPairs": int(len(aW)),
                  "period": {"start": b.rows[Midx[0]][0], "end": b.rows[Midx[-1]][0]},
                  "requiredPairs": K.REQUIRED_PAIRS,
                  "underpowered": bool(len(aW) < K.REQUIRED_PAIRS)},
        "a": a9, "items": item13,
        "W7model": {"n": n7, "R2": r2_7, "weatherLevels": wlev},
        "W": W,
    }


def part_dec(b, window):
    mt = build_match(b, window)
    decmap = load_dec(window)
    rows, Midx, KIM = b.rows, mt.Midx, K.KIMARITE
    nU = len(Midx)
    usid = b.sid[Midx]
    urno = b.rno[Midx]
    ucell = b.cell[Midx]
    u_out = np.zeros(nU, dtype=bool)
    u_k1 = np.full(nU, np.nan)
    u_k3 = np.full(nU, np.nan)
    u_kim = np.full(nU, -1, dtype=np.int64)
    for j, i in enumerate(Midx):
        v = decmap.get((rows[i][0], rows[i][1], rows[i][2]))
        if v is None:
            K.stop("段階11: 突合済みのレースが results に無い: %s" % (rows[i][:3],))
        k1, o1, kim, wc = v
        if k1 is not None:
            u_k1[j] = k1
        if o1 is not None:
            u_out[j] = o1 == 1
        if kim is not None:
            if kim not in KIM:
                K.stop("段階11: 想定外の決まり手 %r（統合せず停止）" % kim)
            u_kim[j] = KIM.index(kim)
        if wc is not None:
            u_k3[j] = wc
    useg = np.r_[True, (usid[1:] != usid[:-1]) | (urno[1:] - urno[:-1] != 1)]
    upa = np.flatnonzero(~useg[1:])
    upb = upa + 1
    if len(upa) != len(mt.aW):
        K.stop("段階11: 隣接ペア数が段階9と一致しない %d != %d" % (len(upa), len(mt.aW)))

    def ucenter(x):
        ok = ~np.isnan(x)
        s = np.bincount(ucell[ok], weights=x[ok], minlength=len(b.ncell))
        c = np.bincount(ucell[ok], minlength=len(b.ncell))
        m = np.divide(s, c, out=np.zeros_like(s), where=c > 0)
        return x - m[ucell]
    u_k1c = ucenter(u_k1)
    u_k3c = ucenter(u_k3)

    def dec_stats(out_b, kim, k1c, k3c):
        hs = {"①着外": K.runhist(out_b, useg)}
        cat = []
        for ci, c in enumerate(KIM):
            h = K.runhist(kim == ci, useg)
            hs["決まり手:" + c] = h
            cat.append(h)
        hs["決まり手:同一カテゴリ計"] = np.sum(cat, axis=0)
        ok = (kim[upa] >= 0) & (kim[upb] >= 0)
        match = float((kim[upa][ok] == kim[upb][ok]).mean())
        cr = {}
        for name, x in (("K1", k1c), ("K3", k3c)):
            m = ~np.isnan(x[upa]) & ~np.isnan(x[upb])
            cr[name] = (K.pearson(x[upa][m], x[upb][m]), int(m.sum()))
        return hs, (match, int(ok.sum())), cr
    obs = dec_stats(u_out, u_kim, u_k1c, u_k3c)
    nhit = {"①着外": int(u_out.sum()), "決まり手:同一カテゴリ計": int((u_kim >= 0).sum())}
    for ci, c in enumerate(KIM):
        nhit["決まり手:" + c] = int((u_kim == ci).sum())
    rng11 = np.random.default_rng(K.SEED)
    usf = usid.astype(float)
    nh = {key: np.empty((K.NREP, 13)) for key in obs[0]}
    nm = np.empty(K.NREP)
    nc = {"K1": np.empty(K.NREP), "K3": np.empty(K.NREP)}
    for k in range(K.NREP):
        pu = np.argsort(usf + rng11.random(nU))
        hs, mtc, cr = dec_stats(u_out[pu], u_kim[pu], u_k1c[pu], u_k3c[pu])
        for key, h in hs.items():
            nh[key][k] = h
        nm[k] = mtc[0]
        for name in nc:
            nc[name][k] = cr[name][0]
        if (k + 1) % 100 == 0:
            print("dec 帰無 %d/%d" % (k + 1, K.NREP), flush=True)

    def streak_n(h_obs, h_null, n_hit):
        out = {}
        short = n_hit < K.MIN_N11
        cols = [(str(k), h_obs[k], h_null[:, k]) for k in range(2, 7)]
        cols.append(("7+", h_obs[7:].sum(), h_null[:, 7:].sum(axis=1)))
        for label, ob, nu in cols:
            dsc = K.describe(nu.astype(float), float(ob))
            out[label] = {
                "observed": int(ob), "nullMean": dsc["mean"], "nullSd": dsc["sd"],
                "ratio": None if short or dsc["mean"] <= 0 else float(ob) / dsc["mean"],
                "pTwoSided": None if short else dsc["pTwoSided"],
                "note": "n不足" if short else ""}
        return out
    st = {key: {"n": nhit[key], "k": streak_n(obs[0][key], nh[key], nhit[key])}
          for key in obs[0]}
    dm = K.describe(nm, obs[1][0])
    m_short = obs[1][1] < K.MIN_N11
    stm = {"n": obs[1][1], "observed": obs[1][0], "nullMean": dm["mean"],
           "nullSd": dm["sd"], "ratio": None if m_short else obs[1][0] / dm["mean"],
           "pTwoSided": None if m_short else dm["pTwoSided"],
           "note": "n不足" if m_short else ""}
    stc = {}
    for name in ("K1", "K3"):
        ob, nn = obs[2][name]
        dc = K.describe(nc[name], ob)
        c_short = nn < K.MIN_N11
        stc[name] = {"n": nn, "observed": ob, "nullA_center": dc["mean"],
                     "sd": dc["sd"], "p2_5": dc["p2_5"], "p97_5": dc["p97_5"],
                     "net": None if c_short else ob - dc["mean"],
                     "pTwoSided": None if c_short else dc["pTwoSided"],
                     "note": "n不足" if c_short else ""}
    return {"races": nU, "adjacentPairs": int(len(upa)),
            "kimariteCounts": {c: nhit["決まり手:" + c] for c in KIM},
            "kimariteMissing": int((u_kim < 0).sum()),
            "streaks": st, "matchRate": stm, "corr": stc}


def speed_band(ms):
    """buildKensho05Wind.py と同一。"""
    if ms <= 1:
        return 0
    if ms <= 3:
        return 1
    if ms <= 5:
        return 2
    return 3


def part_course1(b, window):
    mt = build_match(b, window)
    decmap = load_dec(window)
    rows, Midx, NV = b.rows, mt.Midx, len(b.venues)
    cval = mt.cval
    o4 = [decmap[rows[i][:3]][1] for i in Midx]
    v4 = np.array([x is not None for x in o4])
    i4 = Midx[v4]
    y4 = np.array([x for x in o4 if x is not None], dtype=float)
    j4 = b.ven[i4]
    c4 = np.bincount(j4, minlength=NV)
    pv4 = np.divide(np.bincount(j4, weights=y4, minlength=NV), c4,
                    out=np.zeros(NV), where=c4 > 0)
    r4 = y4 - pv4[j4]
    bands4 = []
    # 風速：buildKensho05Wind.py と同じ帯。風向コード17（無風）は帯に入れず別枠
    wc4 = mt.wcode[i4]
    sb4 = np.array([speed_band(x) for x in mt.wsp[i4]])
    for j, lab in enumerate(["0-1m", "2-3m", "4-5m", "6m以上"]):
        bands4.append(("風速", lab, lab, (sb4 == j) & (wc4 != 17)))
    bands4.append(("風速", "無風", "風向コード17", wc4 == 17))
    wv4 = cval["波高"][i4]
    wb4 = np.where(wv4 <= 1, 0, np.where(wv4 <= 3, 1, np.where(wv4 <= 5, 2, 3)))
    for j, lab in enumerate(["0-1cm", "2-3cm", "4-5cm", "6cm以上"]):
        bands4.append(("波高", lab, lab, wb4 == j))
    qb4 = {}
    for c in ("気温", "水温"):
        x = cval[c][i4]
        srt4 = np.sort(x)
        bq = [float(srt4[int(np.ceil(k * len(x) / 4)) - 1]) for k in (1, 2, 3)]
        qb4[c] = bq
        bb = np.searchsorted(np.array(bq), x, side="left") + 1
        labs = ["<=%g" % bq[0], "%g<x<=%g" % (bq[0], bq[1]),
                "%g<x<=%g" % (bq[1], bq[2]), ">%g" % bq[2]]
        for j in range(4):
            bands4.append((c, "Q%d" % (j + 1), labs[j], bb == j + 1))
    w4 = cval["天候コード"][i4].astype(np.int64)
    for lv in sorted(set(w4.tolist())):
        bands4.append(("天候コード", str(lv), K.WEATHER.get(lv, ""), w4 == lv))
    bands4.append(("全体", "計", "", np.ones(len(i4), dtype=bool)))
    ccrow = []
    for item, band, lab, m in bands4:
        nn = int(m.sum())
        kk = int(y4[m].sum())
        if nn >= K.MIN_N11:
            lo, hi = K.wilson(kk, nn)
            rr = r4[m]
            mr = float(rr.mean())
            h = K.Z95 * float(rr.std(ddof=1)) / math.sqrt(nn)
            ccrow.append([item, band, lab, nn, kk, round(100.0 * kk / nn, 2),
                          round(100.0 * lo, 2), round(100.0 * hi, 2),
                          round(100.0 * mr, 2) + 0.0, round(100.0 * (mr - h), 2) + 0.0,
                          round(100.0 * (mr + h), 2) + 0.0, ""])
        else:
            ccrow.append([item, band, lab, nn, kk, None, None, None, None, None,
                          None, "n不足"])
    return {"races": int(len(i4)), "quartileBounds": qb4,
            "rows": [K.csvcells(r) for r in ccrow]}


def run_part(window, part):
    started = K.jst_now()
    rows, vdays = load_rows(window)
    b = build_base(rows, vdays)
    print("base n=%d series=%d pairs=%d" % (b.n, b.nseries, len(b.a1)), flush=True)
    if part == "flow":
        out = part_flow(b)
    elif part == "cond":
        out = part_cond(b, window)
    elif part == "dec":
        out = part_dec(b, window)
    else:
        out = part_course1(b, window)
    out = K.roundtree(out)
    out["_run"] = {"window": window, "part": part,
                   "startedJST": started.strftime("%Y-%m-%d %H:%M JST"),
                   "finishedJST": K.jst_now().strftime("%Y-%m-%d %H:%M JST")}
    os.makedirs(WORKDIR, exist_ok=True)
    path = os.path.join(WORKDIR, "part_%s_%s.json" % (window, part))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("wrote", path, flush=True)


def load_part(window, part):
    with open(os.path.join(WORKDIR, "part_%s_%s.json" % (window, part)), encoding="utf-8") as f:
        return json.load(f)


def load_existing():
    with open(os.path.join(K.OUTDIR, "summary.json"), encoding="utf-8") as f:
        return json.load(f)


def read_csv(name):
    with open(os.path.join(K.OUTDIR, name), encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


# ---------------------------------------------------------------- 窓A：写しが既存出力と同じか
def check():
    old = load_existing()
    fl, co, de, c1 = (load_part("A", p) for p in PARTS)
    s8 = dict(old["stage8"]["cases"]["S3-D1"])
    pairs = [
        ("stage1/manRate", fl["stage1"]["manRate"], old["stage1"]["manRate"]),
        ("stage1/quintileBounds", fl["stage1"]["quintileBounds"], old["stage1"]["quintileBounds"]),
        ("stage2/series", fl["stage2"]["series"], old["stage2"]["series"]),
        ("stage2/adjacentPairs", fl["stage2"]["adjacentPairs"], old["stage2"]["adjacentPairs"]),
        ("stage2/breaks", fl["stage2"]["breaks"], old["stage2"]["breaks"]),
        ("stage7/S3/nPairs", fl["stage7S3"]["nPairs"], old["stage7"]["sets"]["S3"]["nPairs"]),
        ("stage7/S3/T3q_cell", fl["stage7S3"]["T3q_cell"], old["stage7"]["sets"]["S3"]["T3q_cell"]),
        ("stage7/S3/nullA_eq", fl["stage7S3"]["nullA_eq"], old["stage7"]["sets"]["S3"]["nullA_eq"]),
        ("stage8/S3-D1", fl["stage8S3D1"], s8),
        ("stage10/H", fl["stage10"]["H"], old["stage10"]["streaks"]["H"]),
        ("stage10/L", fl["stage10"]["L"], old["stage10"]["streaks"]["L"]),
        ("stage10/shareBelow05", fl["stage10"]["shareBelow05"],
         old["stage10"]["seriesConcentration"]["shareBelow05"]),
        ("stage9/a", co["a"], {k: v for k, v in old["stage9"]["a"]["vars"].items()}),
        ("stage9/match/adjacentPairs", co["match"]["adjacentPairs"],
         old["stage9"]["match"]["adjacentPairs"]),
        ("stage9/match/matchedRaces", co["match"]["matchedRaces"],
         old["stage9"]["match"]["matchedRaces"]),
        ("stage13/W7/R2", co["W7model"]["R2"], old["stage13"]["control"]["W7model"]["R2"]),
        ("stage11/streaks", de["streaks"], old["stage11"]["streaks"]),
        ("stage11/matchRate", de["matchRate"], old["stage11"]["matchRate"]),
        ("stage11/corr", de["corr"], old["stage11"]["corr"]),
        ("stage13/conditionCourse1/quartileBounds", c1["quartileBounds"],
         old["stage13"]["conditionCourse1"]["quartileBounds"]),
    ]
    for key in ("T1_raw", "T2_venueCentered", "T3_cellCentered", "T4_net", "decomposition"):
        pairs.append(("stage3/" + key, fl["stage3"][key], old["stage3"][key]))
    pairs.append(("stage4/nullA", fl["stage3"]["nullA"], old["stage4"]["nullA"]))
    pairs.append(("stage4/nullB", fl["stage3"]["nullB"], old["stage4"]["nullB"]))
    for key in ("T1q_raw", "T2q_venue", "T3q_cell", "T4q_net", "decomposition",
                "nullA_eq", "nullB_q"):
        pairs.append(("stage6b/" + key, fl["stage6b"][key], old["stage6b"][key]))
    for w in ("W0", "W1", "W7"):
        pairs.append(("stage13/control/" + w,
                      fl_w(co["W"][w]), fl_w(old["stage13"]["control"][w])))
    for name, v in co["items"].items():
        ov = old["stage13"]["mediation"]["items"][name]
        pairs.append(("stage13/items/" + name,
                      {k: v[k] for k in ("a", "aPairs", "b2_R2", "n", "upper")},
                      {k: ov[k] for k in ("a", "aPairs", "b2_R2", "n", "upper")}))
    tq = read_csv("quintileTransition.csv")[1:]
    for lab, v in fl["transitionS0"].items():
        row = [r for r in tq if r[0] == str(v["from"]) and r[1] == str(v["to"])][0]
        pairs.append(("quintileTransition " + lab, [str(v["n"]), str(v["rowPct"])], row[2:4]))
    cc_old = read_csv("conditionCourse1.csv")[1:]
    cc_new = [["" if x is None else str(x) for x in r] for r in c1["rows"]
              if r[0] != "風速"]
    pairs.append(("conditionCourse1.csv", cc_new, cc_old))
    bad = [(k, a, b) for k, a, b in pairs if a != b]
    for k, a, b in bad:
        print("CHECK NG: %s / 既存 %s / 写し %s" % (k, b, a))
    print("check: %d項目中 不一致 %d" % (len(pairs), len(bad)))
    return len(pairs), bad


def fl_w(v):
    return {k: v[k] for k in ("nPairs", "T3q", "nullA_eq", "net", "pTwoSided", "insideNull95")}


# ---------------------------------------------------------------- 窓B：stage14 と CSV
def changed(a, b, kind):
    """符号・大小関係の変化。kind: sign（0との大小）/ ratio（1との大小）/ sig（p<0.05）"""
    if a is None or b is None:
        return ""
    if kind == "sign":
        return "符号が変わった" if (a > 0) != (b > 0) else ""
    if kind == "ratio":
        return "1との大小が変わった" if (a > 1) != (b > 1) else ""
    if kind == "sig":
        return "有意性(p<0.05)が変わった" if (a < 0.05) != (b < 0.05) else ""
    return ""


def write():
    old = load_existing()
    ncheck, bad = check()
    if bad:
        K.stop("窓A の写しが既存出力と一致しない。stage14 を書かない")
    fl, co, de, c1 = (load_part("B", p) for p in PARTS)
    runs = {p: load_part("B", p)["_run"] for p in PARTS}
    for p in (fl, co, de, c1):
        p.pop("_run", None)

    A, S9 = "分母A(10年)", "分母B(409日)"
    rows = []

    def add(section, metric, va, vb, ref, kind=""):
        rows.append([section, metric, ref, va, vb, changed(va, vb, kind) if kind else ""])

    # 作業1
    for key, va, vb in (("races", old["stage1"]["n"], fl["stage1"]["n"]),
                        ("series", old["stage2"]["series"], fl["stage2"]["series"]),
                        ("adjacentPairs", old["stage2"]["adjacentPairs"], fl["stage2"]["adjacentPairs"]),
                        ("breaks", old["stage2"]["breaks"], fl["stage2"]["breaks"]),
                        ("manRate", old["stage1"]["manRate"], fl["stage1"]["manRate"])):
        add("作業1", key, va, vb, A)
    for i in range(4):
        add("作業1", "quintileBound%d" % (i + 1), old["stage1"]["quintileBounds"][i],
            fl["stage1"]["quintileBounds"][i], A)
    # 作業2
    s3o, s3b = old["stage3"], fl["stage3"]
    for key in ("T1_raw", "T2_venueCentered", "T3_cellCentered", "T4_net"):
        add("2-1", key, s3o[key], s3b[key], A, "sign")
    for key in ("venueDiff_T1minusT2", "rShape_T2minusT3", "dayCommon_T3minusT4"):
        add("2-1", key, s3o["decomposition"][key], s3b["decomposition"][key], A, "sign")
    add("2-1", "nullA_mean", old["stage4"]["nullA"]["mean"], s3b["nullA"]["mean"], A, "sign")
    add("2-1", "nullA_p", old["stage4"]["nullA"]["pTwoSided"], s3b["nullA"]["pTwoSided"], A, "sig")
    add("2-1", "nullB_mean", old["stage4"]["nullB"]["mean"], s3b["nullB"]["mean"], A, "sign")
    s6o, s6b = old["stage6b"], fl["stage6b"]
    for key in ("T1q_raw", "T2q_venue", "T3q_cell", "T4q_net"):
        add("2-2", key, s6o[key], s6b[key], A, "sign")
    for key in ("venueDiff_T1qminusT2q", "rShape_T2qminusT3q", "dayCommon_T3qminusT4q"):
        add("2-2", key, s6o["decomposition"][key], s6b["decomposition"][key], A, "sign")
    add("2-2", "nullA_eq_mean", s6o["nullA_eq"]["mean"], s6b["nullA_eq"]["mean"], A, "sign")
    add("2-2", "nullA_eq_p", s6o["nullA_eq"]["pTwoSided"], s6b["nullA_eq"]["pTwoSided"], A, "sig")
    add("2-2", "nullB_q_mean", s6o["nullB_q"]["mean"], s6b["nullB_q"]["mean"], A, "sign")
    o8, b8 = old["stage8"]["cases"]["S3-D1"], fl["stage8S3D1"]
    add("2-3", "S3-D1 nPairs", o8["nPairs"], b8["nPairs"], A)
    add("2-3", "S3-D1 T3q", o8["T3q"], b8["T3q"], A, "sign")
    add("2-3", "S3-D1 net", o8["net"], b8["net"], A, "sign")
    add("2-3", "S3-D1 p", o8["pTwoSided"], b8["pTwoSided"], A, "sig")
    for typ, lab in (("H", "万舟"), ("L", "最安")):
        for kk in ("2", "3", "4", "5", "6"):
            vo, vb = old["stage10"]["streaks"][typ][kk], fl["stage10"][typ][kk]
            add("2-4", "%s k=%s observed" % (lab, kk), vo["observed"], vb["observed"], A)
            add("2-4", "%s k=%s nullMean" % (lab, kk), vo["nullMean"], vb["nullMean"], A)
            add("2-4", "%s k=%s ratio" % (lab, kk), vo["ratio"], vb["ratio"], A, "ratio")
            add("2-4", "%s k=%s p" % (lab, kk), vo["pTwoSided"], vb["pTwoSided"], A, "sig")
    oc = old["stage10"]["seriesConcentration"]
    add("2-5", "nBelow05", oc["nBelow05"], fl["stage10"]["nBelow05"], A)
    add("2-5", "shareBelow05", oc["shareBelow05"], fl["stage10"]["shareBelow05"], A)
    tq = read_csv("quintileTransition.csv")[1:]
    for lab, v in fl["transitionS0"].items():
        f = str(v["from"])
        rowsA = [r for r in tq if r[0] == f]
        na = int([r for r in rowsA if r[1] == f][0][2])
        ta = sum(int(r[2]) for r in rowsA)
        add("2-6", lab + " rowPct", float([r for r in rowsA if r[1] == f][0][3]), v["rowPct"], A)
        add("2-6", lab + " n", na, v["n"], A)
        add("2-6", lab + " rowTotal", ta, v["rowTotal"], A)
    # 作業3（409日と並べる）
    s11 = old["stage11"]
    for key, ks in (("①着外", ("2", "3", "4", "5", "6")), ("決まり手:逃げ", ("2", "3", "4", "5"))):
        for kk in ks:
            vo, vb = s11["streaks"][key]["k"][kk], de["streaks"][key]["k"][kk]
            add("作業3", "%s k=%s observed" % (key, kk), vo["observed"], vb["observed"], S9)
            add("作業3", "%s k=%s nullMean" % (key, kk), vo["nullMean"], vb["nullMean"], S9)
            add("作業3", "%s k=%s ratio" % (key, kk), vo["ratio"], vb["ratio"], S9, "ratio")
            add("作業3", "%s k=%s p" % (key, kk), vo["pTwoSided"], vb["pTwoSided"], S9, "sig")
    for f in ("observed", "nullMean", "ratio", "pTwoSided", "n"):
        add("作業3", "決まり手一致率 " + f, s11["matchRate"][f], de["matchRate"][f], S9,
            {"ratio": "ratio", "pTwoSided": "sig"}.get(f, ""))
    for name in ("K1", "K3"):
        for f in ("observed", "nullA_center", "net", "pTwoSided", "n"):
            add("作業3", "%s %s" % (name, f), s11["corr"][name][f], de["corr"][name][f], S9,
                {"net": "sign", "pTwoSided": "sig"}.get(f, ""))
    # 作業4（409日と並べる）
    s13 = old["stage13"]
    add("作業4", "matchedRaces", s13["rows"]["races"], co["match"]["matchedRaces"], S9)
    add("作業4", "adjacentPairs", s13["rows"]["adjacentPairs"], co["match"]["adjacentPairs"], S9)
    for name, v in co["items"].items():
        ov = s13["mediation"]["items"][name]
        add("作業4", name + " a", ov["a"], v["a"], S9, "sign")
        add("作業4", name + " b2_R2", ov["b2_R2"], v["b2_R2"], S9)
        add("作業4", name + " upper", ov["upper"], v["upper"], S9, "sign")
    add("作業4", "referenceResidual_S3D1net", s13["mediation"]["referenceResidual_S3D1net"],
        b8["net"], A + "→窓B", "sign")
    for w, lab in (("W0", "W0"), ("W7", "W6(6項目統制)")):
        ov, v = s13["control"][w], co["W"][w]
        add("作業4", lab + " T3q", ov["T3q"], v["T3q"], S9, "sign")
        add("作業4", lab + " nullA_eq_mean", ov["nullA_eq"]["mean"], v["nullA_eq"]["mean"], S9)
        add("作業4", lab + " net", ov["net"], v["net"], S9, "sign")
        add("作業4", lab + " p", ov["pTwoSided"], v["pTwoSided"], S9, "sig")
        add("作業4", lab + " insideNull95", ov["insideNull95"], v["insideNull95"], S9)

    header = ["section", "metric", "compareWith", "reference", "windowB", "change"]
    K.write_csv(os.path.join(K.OUTDIR, "windowBCompare.csv"), header, rows)
    K.write_csv(os.path.join(K.OUTDIR, "conditionCourse1WindowB.csv"),
                ["item", "band", "range", "n", "out", "rate", "ciLow", "ciHigh",
                 "residMeanPt", "residCiLowPt", "residCiHighPt", "note"], c1["rows"])

    stage14 = {
        "definition": "窓B＝2017-10-25〜2026-09-01。payrank 採用行をこの期間に限り、results は v2 取り直し分（〜2025-07-14、C:\\Users\\USER\\boatraceResults\\json）と既存 results/（2025-07-15〜）を足して突合。手順（中心化・ペア定義・統計量・帰無A/B・1,000回・seed 20260914）は段階3・6b・7・8・9・10・11・13と同一",
        "script": "scripts/buildKensho05WindowB.py",
        "runs": runs,
        "seedNote": "各パートは default_rng(20260914) から開始し、置換は perm = argsort(系列番号 + rng.random(n))（段階6bと同一）。1回あたりの乱数消費は n 個で計算する統計量に依存しないため、パートを別プロセスに分けても置換は同一。系列ごとに seed+系列インデックス を使う方式は段階6bと置換が変わるため採らない",
        "procedureCheck": {"definition": "同じスクリプトを窓A（10年・results 2025-07-15〜2026-09-13）で回し、既存の stage1〜stage13 と CSV の該当値に一致することを確認してから窓Bを書く",
                           "items": ncheck, "mismatches": len(bad)},
        "quintileNote": "五分位の境界は窓Bの行だけで引き直した（10年の境界は流用していない）。10年の境界は stage1.quintileBounds",
        "work1_denominator": dict(fl["stage1"], **fl["stage2"],
                                  reference10y={"n": old["stage1"]["n"],
                                                "series": old["stage2"]["series"],
                                                "adjacentPairs": old["stage2"]["adjacentPairs"],
                                                "breaks": old["stage2"]["breaks"],
                                                "manRate": old["stage1"]["manRate"],
                                                "quintileBounds": old["stage1"]["quintileBounds"]}),
        "work2_flow": {"stage3": fl["stage3"], "stage6b": fl["stage6b"],
                       "stage7S3": fl["stage7S3"], "stage8S3D1": fl["stage8S3D1"],
                       "stage10": fl["stage10"], "transitionS0": fl["transitionS0"],
                       "transitionMatrix": fl["transitionMatrix"]},
        "work3_decision": de,
        "work4_conditions": dict(co, note="items の 風向コード は 角度 と 水面成分 の2通り。W7 は6項目すべての統制（指示上の W6）"),
        "work5_conditionCourse1": {"file": "conditionCourse1WindowB.csv", "races": c1["races"],
                                   "quartileBounds": c1["quartileBounds"],
                                   "windBands": "0-1 / 2-3 / 4-5 / 6m以上（buildKensho05Wind.py と同じ帯）。風向コード17は帯に入れず 無風 の別枠",
                                   "nRule": "n が300未満のセルは率・区間・残差を出さず note に n不足",
                                   "residual": "段階13 作業4と同一（その場の①着外率を引いた残差の平均・正規近似95%・pt）"},
        "compareFile": "windowBCompare.csv",
        "changes": [r for r in rows if r[5]],
    }
    stage14 = K.roundtree(stage14)
    old["stage14"] = stage14
    with open(os.path.join(K.OUTDIR, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(old, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("stage14 written. changes=%d" % len(stage14["changes"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "check", "write"))
    ap.add_argument("--window", choices=("A", "B"))
    ap.add_argument("--part", choices=PARTS)
    args = ap.parse_args()
    if args.cmd == "run":
        if not args.window or not args.part:
            K.stop("run には --window と --part が要る")
        run_part(args.window, args.part)
    elif args.cmd == "check":
        _, bad = check()
        sys.exit(1 if bad else 0)
    else:
        write()


if __name__ == "__main__":
    main()
