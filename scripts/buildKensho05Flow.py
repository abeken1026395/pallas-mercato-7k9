# -*- coding: utf-8 -*-
# buildKensho05Flow.py
# 検証05「流れ」はあるか。
# 同じ開催日・同じ場のレース列（系列）の中で、万舟（3連単払戻 >= 10,000円）が
# 隣のレースへ「続く」ように見えるかを、中心化の段階と帰無分布で分解して数える。
#
# 入力 : payrank/json/*.json（リポジトリ外・読み取り専用）。1行＝1レース。
# 出力 : analysis/kensho05/ に集計結果のみ（生データは置かない）
#   summary.json / cellRates.csv / distanceCorr.csv / dayDispersion.csv /
#   quintileTransition.csv / nullDist.csv / distanceCorrQ.csv /
#   quintileTransitionS3.csv
#
# 段階0 の分母アサートが1つでも外れたら、何も書かずに終了コード1で止まる。
#
# 使い方:
#   python scripts/buildKensho05Flow.py [入力ディレクトリ]
import os
import sys
import csv
import json
import math
import datetime

import numpy as np

INDIR = r"C:\Users\USER\payrank\json"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "analysis", "kensho05")

RESULTS_DIR = os.path.join(ROOT, "results")
RESULTS_TO = "20260913"   # results の最終確定日（buildKensho05Wind.py と同じ）
BEARING_PATH = os.path.join(ROOT, "docs", "data", "stadiumBearing.json")
MISSING_MONTH_MAX = 0.10
REQUIRED_PAIRS = 55500

SEED = 20260914
NREP = 1000
MAN = 10000
DMAX = 11
NQ = 5

EXPECT = [
    ("総行数", "total", 557172),
    ("除外合計", "excluded", 22842),
    ("採用", "adopted", 534330),
    ("開催日数", "days", 3653),
    ('"-"0個', "dash0", 6945),
    ("うち中止", "dash0Chushi", 6866),
    ("うちその他", "dash0Other", 79),
    ('"-"1個', "dash1", 227),
    ('"-"5個', "dash5", 209),
    ("人気非数字", "ninkiNonNum", 15461),
]


def jst_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))


def stop(msg):
    print("STOP: " + msg)
    sys.exit(1)


# ---------------------------------------------------------------- 段階0
def load(indir):
    """全ファイルを読み、除外を排他に判定して採用行を返す。"""
    try:
        names = sorted(n for n in os.listdir(indir) if n.endswith(".json"))
    except OSError as ex:
        stop("入力ディレクトリが読めない: %s" % ex)
    cnt = dict(total=0, dash0=0, dash0Chushi=0, dash0Other=0, dash1=0,
               dash5=0, dashOther=0, ninkiNonNum=0)
    days = set()
    vdays = set()
    rows = []
    for n in names:
        with open(os.path.join(indir, n), encoding="utf-8") as f:
            d = json.load(f)
        hd = d["開催日"]
        for r in d["払戻"]:
            cnt["total"] += 1
            days.add(hd)
            vdays.add((hd, r["場コード"]))
            kumi = r["組番"]
            k = kumi.count("-")
            if k == 0:
                cnt["dash0"] += 1
                if kumi == "レース中止":
                    cnt["dash0Chushi"] += 1
                else:
                    cnt["dash0Other"] += 1
                continue
            if k == 1:
                cnt["dash1"] += 1
                continue
            if k == 5:
                cnt["dash5"] += 1
                continue
            if k != 2:
                cnt["dashOther"] += 1
                continue
            if not r["人気"].isdigit():
                cnt["ninkiNonNum"] += 1
                continue
            pay = r["払戻"]
            if not pay.startswith("\u00a5"):
                stop("採用行の払戻が想定外の形式: %r (%s)" % (pay, n))
            race = r["レース"]
            if not race.endswith("R"):
                stop("レース列が想定外の形式: %r (%s)" % (race, n))
            rows.append((hd, r["場コード"], int(race[:-1]),
                         int(pay[1:].replace(",", ""))))
    cnt["days"] = len(days)
    cnt["adopted"] = len(rows)
    cnt["excluded"] = (cnt["dash0"] + cnt["dash1"] + cnt["dash5"]
                       + cnt["dashOther"] + cnt["ninkiNonNum"])
    return cnt, rows, vdays


def build_setsu(vdays):
    """同一場で日付を昇順に並べ、1日ずつ連続する塊を1節とする。
    返り値: {(開催日, 場): (節の何日目, 節の日数)}, 節の日数のリスト"""
    byv = {}
    for hd, v in vdays:
        byv.setdefault(v, []).append(
            datetime.date(int(hd[:4]), int(hd[4:6]), int(hd[6:])))
    info = {}
    lens = []
    for v, ds in byv.items():
        ds.sort()
        block = [ds[0]]
        for d in ds[1:] + [None]:
            if d is not None and (d - block[-1]).days == 1:
                block.append(d)
                continue
            lens.append(len(block))
            for i, b in enumerate(block):
                info[(b.strftime("%Y%m%d"), v)] = (i + 1, len(block))
            block = [d]
    return info, lens


def detrend_prep(sid, x, slen, deg):
    """系列ごとの多項式回帰（切片つき）の準備。
    返り値: 説明変数行列, 系列ごとの (X'X)^-1, 残す系列のマスク"""
    ns = len(slen)
    X = np.vstack([x ** p for p in range(deg + 1)]).T
    k = deg + 1
    xtx = np.zeros((ns, k, k))
    for i in range(k):
        for j in range(k):
            xtx[:, i, j] = np.bincount(sid, weights=X[:, i] * X[:, j],
                                       minlength=ns)
    keep = slen >= deg + 2
    inv = np.zeros_like(xtx)
    inv[keep] = np.linalg.inv(xtx[keep])
    return X, inv, keep


def detrend(y, sid, ns, X, inv, keep):
    """系列ごとに y を X に回帰した残差。除外系列は係数0（使わない）。"""
    xty = np.stack([np.bincount(sid, weights=X[:, i] * y, minlength=ns)
                    for i in range(X.shape[1])], axis=1)
    beta = np.einsum("sij,sj->si", inv, xty)
    return y - (X * beta[sid]).sum(axis=1)


def detrend_check(res, sid, ns, X, inv, keep):
    """残す系列で残差が各説明変数と直交しているか（最大絶対値）。"""
    worst = 0.0
    for i in range(X.shape[1]):
        g = np.bincount(sid, weights=X[:, i] * res, minlength=ns)[keep]
        worst = max(worst, float(np.abs(g).max()))
    return worst


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def load_results(dirpath, date_to):
    """results/YYYYMMDD.json → {(開催日, 場コード'NN', R int): (風速, 風向コード)}。
    results は 場コード="01" 文字列・レース="1R" 文字列なので int に変換してキーを揃える。"""
    out = {}
    names = sorted(n for n in os.listdir(dirpath)
                   if len(n) == 13 and n.endswith(".json") and n[:8].isdigit()
                   and n[:8] <= date_to)
    for name in names:
        hd = name[:8]
        with open(os.path.join(dirpath, name), encoding="utf-8") as f:
            d = json.load(f)
        for r in d.get("結果", []) or []:
            jcd = str(r.get("場コード", "")).zfill(2)
            race = str(r.get("レース", ""))
            if not race.endswith("R") or not race[:-1].isdigit():
                stop("results のレース列が想定外: %r (%s)" % (race, name))
            key = (hd, jcd, int(race[:-1]))
            if key in out:
                stop("results に同じレースが重複: %s" % (key,))
            out[key] = (r.get("風速"), r.get("風向コード"))
    return out, (names[0][:8], names[-1][:8])


def water_component(bearing, code):
    """facts.md の判定式（docs/results/index.html の windRel と同一）。
    追い風=+1 / 横風=0 / 向かい風=-1。17=無風は None（欠測）。"""
    if code == 17:
        return None
    d = (code - 1) * 22.5
    diff = abs((((d - bearing + 180) % 360) + 360) % 360 - 180)
    if diff <= 45:
        return 1
    if diff >= 135:
        return -1
    return 0


def ols(X, y):
    """最小二乗。係数・標準誤差（通常のOLS）・R²・n を返す。"""
    n, k = X.shape
    if np.linalg.matrix_rank(X) != k:
        stop("回帰の説明変数が退化している")
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ (X.T @ y)
    res = y - X @ beta
    rss = float(res @ res)
    tss = float(((y - y.mean()) ** 2).sum())
    se = np.sqrt(np.diag(xtx_inv) * rss / (n - k))
    return beta, se, 1 - rss / tss, n


def lendist7(lens):
    c = np.bincount(np.array(lens), minlength=8)
    out = {str(L): int(c[L]) for L in range(1, 7)}
    out["7+"] = int(c[7:].sum())
    return out


def assert_stage0(cnt):
    bad = [(label, exp, cnt[key]) for label, key, exp in EXPECT
           if cnt[key] != exp]
    if cnt["dashOther"] != 0:
        bad.append(('"-"が0/1/2/5以外', 0, cnt["dashOther"]))
    if cnt["total"] != cnt["excluded"] + cnt["adopted"]:
        bad.append(("総行数=除外+採用", cnt["total"],
                    cnt["excluded"] + cnt["adopted"]))
    if bad:
        for label, exp, got in bad:
            print("ASSERT NG: %s / 期待 %s / 実測 %s" % (label, exp, got))
        stop("段階0のアサート不一致。何も書かない。")
    print("段階0 OK: " + ", ".join("%s=%d" % (lab, cnt[k])
                                   for lab, k, _ in EXPECT))


# ---------------------------------------------------------------- 統計の部品
def pearson(x, y):
    xm = x - x.mean()
    ym = y - y.mean()
    den = np.sqrt((xm @ xm) * (ym @ ym))
    return float((xm @ ym) / den) if den > 0 else float("nan")


def avgrank(v):
    """1..NQ の整数列の平均順位（同順位は平均）。"""
    c = np.bincount(v, minlength=NQ + 1)[1:].astype(float)
    r = np.cumsum(c) - c + (c + 1) / 2
    return r[v - 1]


def spearman(x, y):
    return pearson(avgrank(x), avgrank(y))


def describe(null, obs):
    """帰無分布の要約と観測値の両側p値。
    p = min(1, 2*min((1+#{null>=obs})/(1+B), (1+#{null<=obs})/(1+B)))"""
    b = len(null)
    ge = int((null >= obs).sum())
    le = int((null <= obs).sum())
    p = min(1.0, 2 * min((1 + ge) / (1 + b), (1 + le) / (1 + b)))
    return {
        "reps": b,
        "mean": float(null.mean()),
        "median": float(np.median(null)),
        "sd": float(null.std(ddof=1)),
        "p2_5": float(np.percentile(null, 2.5)),
        "p50": float(np.percentile(null, 50)),
        "p97_5": float(np.percentile(null, 97.5)),
        "observed": obs,
        "pTwoSided": p,
    }


def r6(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) \
        else round(float(x), 6)


def roundtree(o):
    if isinstance(o, dict):
        return {k: roundtree(v) for k, v in o.items()}
    if isinstance(o, list):
        return [roundtree(v) for v in o]
    if isinstance(o, float):
        return r6(o)
    return o


def csvcells(row):
    return [r6(v) if isinstance(v, float) else v for v in row]


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow(csvcells(row))


# 過去の出力とキー名が変わった項目（前の名前 → 今の名前）
RENAMED = {("stage3", "decomposition", "finiteSeriesBias_T3minusT4"):
           ("stage3", "decomposition", "dayCommon_T3minusT4")}
# 値の出どころが同じ別項目と照合する（前の場所 → 今の場所）
RELOCATED = {("stage5", "finiteSeriesBias_nullACenter"): ("stage4", "nullA", "mean")}
# 今回足した項目（前の出力には無い）
ADDED = {("stage5", "finiteSeriesBias_nullBCenter"): ("stage4", "nullB", "mean"),
         ("stage5", "finiteSeriesBiasNote"): None}
CHECKED = ["stage0", "stage1", "stage2", "stage3", "stage4", "stage5", "stage6",
           "stage6b", "stage7", "stage8"]
# 既存出力にあれば照合する（後から足した段階）
CHECKED_IF_PRESENT = ["stage9"]
# 後から足したCSV（既存出力に無ければ照合しない）
NEW_CSVS = {"distanceCorrQ.csv", "quintileTransitionS3.csv", "windMediation.csv"}


def getpath(o, path):
    for k in path:
        o = o[k]
    return o


def flatten(o, prefix=()):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            out.update(flatten(v, prefix + (k,)))
        return out
    return {prefix: o}


def check_repro(summary, csvs):
    """既存の analysis/kensho05/ と比べ、変わった項目を (項目, 前, 後) で返す。
    既存出力が無ければ空（初回）。"""
    sp = os.path.join(OUTDIR, "summary.json")
    if not os.path.exists(sp):
        return []
    with open(sp, encoding="utf-8") as f:
        old = json.load(f)
    diffs = []
    oldf, newf = {}, {}
    for st in CHECKED:
        if st not in old:
            diffs.append((st, "(なし)", "(あり)"))
            continue
        oldf.update(flatten(old[st], (st,)))
        newf.update(flatten(summary[st], (st,)))
    for st in CHECKED_IF_PRESENT:
        if st in old:
            oldf.update(flatten(old[st], (st,)))
            newf.update(flatten(summary[st], (st,)))
    for op, np_ in RENAMED.items():
        if op in oldf:
            oldf[np_] = oldf.pop(op)
    for op, src in RELOCATED.items():
        if op in oldf:
            v = oldf.pop(op)
            if v != getpath(summary, src):
                diffs.append(("/".join(op), v, getpath(summary, src)))
    for np_, src in ADDED.items():
        if np_ in oldf:
            continue
        v = newf.pop(np_, None)
        if src is not None and v != getpath(old, src):
            diffs.append(("/".join(np_), getpath(old, src), v))
    for k in sorted(set(oldf) | set(newf), key=str):
        if oldf.get(k, "(なし)") != newf.get(k, "(なし)"):
            diffs.append(("/".join(map(str, k)), oldf.get(k, "(なし)"),
                          newf.get(k, "(なし)")))
    for name, (header, rows) in csvs.items():
        p = os.path.join(OUTDIR, name)
        if name in NEW_CSVS and not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", newline="") as f:
            oldrows = list(csv.reader(f))
        w = len(oldrows[0])
        if header[:w] != oldrows[0]:
            diffs.append((name + " header", oldrows[0], header[:w]))
        newrows = [["" if v is None else str(v) for v in csvcells(r)][:w]
                   for r in rows]
        if len(newrows) != len(oldrows) - 1:
            diffs.append((name + " rows", len(oldrows) - 1, len(newrows)))
        for i, (a, b) in enumerate(zip(oldrows[1:], newrows)):
            if a != b:
                diffs.append(("%s row%d" % (name, i + 1), a, b))
    return diffs


# ---------------------------------------------------------------- 本体
def main():
    indir = sys.argv[1] if len(sys.argv) > 1 else INDIR
    started = jst_now()
    cnt, rows, vdays = load(indir)
    assert_stage0(cnt)

    # 系列キー(開催日, 場)、系列内はR昇順
    rows.sort(key=lambda t: (t[0], t[1], t[2]))
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
        stop("R が 1..12 の外にある")
    same = sid[1:] == sid[:-1]
    if np.any(same & (rno[1:] == rno[:-1])):
        stop("同一系列に同じRが複数ある（重複行）")

    # ------------------------------------------------------------ 段階1
    yA = (pay >= MAN).astype(np.int64)
    srt = np.sort(pay)
    bounds = [int(srt[int(np.ceil(k * n / NQ)) - 1]) for k in range(1, NQ)]
    # 同額は下位帯へ：pay <= b1 → 1、b1 < pay <= b2 → 2 …
    q = np.searchsorted(np.array(bounds), pay, side="left").astype(np.int64) + 1
    qcount = np.bincount(q, minlength=NQ + 1)[1:]

    # ------------------------------------------------------------ 段階2
    nseries = int(sid[-1]) + 1
    slen = np.bincount(sid)
    lendist = {str(L): int((slen == L).sum()) for L in range(12, 0, -1)}
    dR1 = rno[1:] - rno[:-1]
    breaks = int((same & (dR1 >= 2)).sum())
    # 距離ペア：同一系列で R差がちょうど d（d=1..DMAX）
    pairs = {}
    for d in range(1, DMAX + 1):
        aa, bb = [], []
        for s in range(1, d + 1):
            i = np.arange(n - s)
            m = (sid[i + s] == sid[i]) & (rno[i + s] - rno[i] == d)
            aa.append(i[m])
            bb.append(i[m] + s)
        pairs[d] = (np.concatenate(aa), np.concatenate(bb))
    a1, b1 = pairs[1]

    # ------------------------------------------------------------ 段階3
    cell = ven * 12 + (rno - 1)
    ncell = np.bincount(cell, minlength=len(venues) * 12)
    mcell = np.bincount(cell, weights=yA, minlength=len(venues) * 12)
    if len(venues) != 24 or int((ncell > 0).sum()) != 288:
        stop("(場,R)セルが288にならない: 場%d / 非空セル%d"
             % (len(venues), int((ncell > 0).sum())))
    pcell = mcell / ncell
    pven = (np.bincount(ven, weights=yA) / np.bincount(ven))
    yf = yA.astype(float)
    zV = yf - pven[ven]
    e = yf - pcell[cell]
    T1 = pearson(yf[a1], yf[b1])
    T2 = pearson(zV[a1], zV[b1])
    T3 = pearson(e[a1], e[b1])
    Td = {d: pearson(e[pairs[d][0]], e[pairs[d][1]]) for d in pairs}

    # 段階6 の観測値
    S_obs = spearman(q[a1], q[b1])

    # 段階6b：q を段階3と同じ手順で中心化し Pearson で出す
    qf = q.astype(float)
    mqcell = np.bincount(cell, weights=qf, minlength=len(venues) * 12) / ncell
    mqven = np.bincount(ven, weights=qf) / np.bincount(ven)
    zVq = qf - mqven[ven]
    eq = qf - mqcell[cell]
    T1q = pearson(qf[a1], qf[b1])
    T2q = pearson(zVq[a1], zVq[b1])
    T3q = pearson(eq[a1], eq[b1])

    # 段階7：節の復元とペア集合の差し替え（中心化・統計量・帰無は段階6bと同一）
    # 開催日＝入力にその場の行がある日（全行が除外の日も含む）
    setsu, setsu_lens = build_setsu(vdays)
    _, setsu_lens_adopted = build_setsu({(t[0], t[1]) for t in rows})
    starts = np.flatnonzero(np.r_[True, sid[1:] != sid[:-1]])
    s_day = np.empty(nseries, dtype=np.int64)
    s_len = np.empty(nseries, dtype=np.int64)
    for s, i in enumerate(starts):
        key = (rows[i][0], rows[i][1])
        if key not in setsu:
            stop("系列が節に割り当てられない: %s" % (key,))
        s_day[s], s_len[s] = setsu[key]
    s_last = s_day == s_len
    s_pen = s_day == s_len - 1
    la = s_last[sid[a1]]
    pa = s_pen[sid[a1]]
    SDEF = {
        "S0": "全ペア（段階6bの再掲）",
        "S1": "節の最終日の系列を除外",
        "S2": "節の最終日と前日の系列を除外",
        "S3": "S2 に加えて、ペアの片方でも R>=10 のものを除外",
    }
    smask = {
        "S0": np.ones(len(a1), dtype=bool),
        "S1": ~la,
        "S2": ~(la | pa),
        "S3": ~(la | pa) & (rno[a1] < 10) & (rno[b1] < 10),
    }
    spairs = {k: (a1[m], b1[m]) for k, m in smask.items()}
    T3qS = {k: pearson(eq[aa], eq[bb]) for k, (aa, bb) in spairs.items()}
    Tqd = {d: pearson(eq[pairs[d][0]], eq[pairs[d][1]]) for d in pairs}

    # 段階8：系列内で eq を R の多項式に回帰した残差で統計量を計算（日内トレンドの除去）
    # 系列長 < 次数+2 の系列は系列ごと除外。帰無側は並べ替え後に同じ残差化を行う。
    Rc = rno.astype(float) - 6.5
    DDEG = {"D0": None, "D1": 1, "D2": 2}
    dprep = {D: detrend_prep(sid, Rc, slen, deg)
             for D, deg in DDEG.items() if deg is not None}
    c8 = {}
    for S in ("S0", "S3"):
        aa0, bb0 = spairs[S]
        for D, deg in DDEG.items():
            if deg is None:
                c8[(S, D)] = dict(pairs=(aa0, bb0), exSeries=0, exSeriesInSet=0,
                                  exPairs=0)
                continue
            keep_s = dprep[D][2]
            m = keep_s[sid[aa0]]
            c8[(S, D)] = dict(
                pairs=(aa0[m], bb0[m]),
                exSeries=int((~keep_s).sum()),
                exSeriesInSet=int(np.unique(sid[aa0[~m]]).size),
                exPairs=int((~m).sum()))
    res8 = {"D0": eq}
    for D in dprep:
        res8[D] = detrend(eq, sid, nseries, *dprep[D])
        chk = detrend_check(res8[D], sid, nseries, *dprep[D])
        if chk > 1e-8:
            stop("残差化の直交性が崩れている: %s %.3g" % (D, chk))
    T8 = {key: pearson(res8[key[1]][v["pairs"][0]], res8[key[1]][v["pairs"][1]])
          for key, v in c8.items()}

    # 段階9：風。作業1 突合（開催日・場・R）
    resmap, res_files = load_results(RESULTS_DIR, RESULTS_TO)
    with open(BEARING_PATH, encoding="utf-8") as f:
        bearing = {j: float(v["方位"]) for j, v in json.load(f)["場"].items()}
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
        if is_int(ms) and is_int(code) and 1 <= code <= 17:
            wsp[i] = ms
            wcode[i] = code
        else:
            wmiss[i] = True
    monthly = []
    excluded_months = []
    for mo in sorted(set(months[have].tolist())):
        mm = months == mo
        nm = int((have & mm).sum())
        nmiss = int((wmiss & mm).sum())
        rate = nmiss / nm
        monthly.append({"month": mo, "adopted": int(mm.sum()), "matched": nm,
                        "windMissing": nmiss, "missingRate": rate})
        if rate > MISSING_MONTH_MAX:
            excluded_months.append(mo)
    M = have & ~wmiss & ~np.isin(months, excluded_months)
    Midx = np.flatnonzero(M)
    mdates = [rows[i][0] for i in Midx]
    in_period = {k for k in resmap
                 if mdates and mdates[0] <= k[0] <= mdates[-1]}
    mkeys = {(rows[i][0], rows[i][1], rows[i][2]) for i in Midx}
    mW = M[a1] & M[b1]
    aW, bW = a1[mW], b1[mW]

    # 作業2 a：風の隣接自己相関（(場,R)セルで中心化。17=無風は角度・水面成分では欠測）
    ang = np.where(M & (wcode >= 1) & (wcode <= 16),
                   np.deg2rad((wcode - 1) * 22.5), np.nan)
    comp = np.full(n, np.nan)
    for i in Midx:
        c = water_component(bearing[rows[i][1]], int(wcode[i]))
        if c is not None:
            comp[i] = c
    wvars = {"speed": np.where(M, wsp, np.nan), "sin": np.sin(ang),
             "cos": np.cos(ang), "component": comp}

    def cell_center(x):
        ok = ~np.isnan(x)
        s = np.bincount(cell[ok], weights=x[ok], minlength=len(ncell))
        c = np.bincount(cell[ok], minlength=len(ncell))
        m = np.divide(s, c, out=np.zeros_like(s), where=c > 0)
        return x - m[cell]
    a9 = {}
    for name, x in wvars.items():
        xc = cell_center(x)
        ok = ~np.isnan(xc[aW]) & ~np.isnan(xc[bW])
        a9[name] = {"r": pearson(xc[aW][ok], xc[bW][ok]),
                    "nPairs": int(ok.sum())}

    # 作業3 b：eq を風に回帰（突合できた行）
    lvl = np.array(["無風" if wcode[i] == 17 else
                    {1: "追い風", 0: "横風", -1: "向かい風"}[int(comp[i])]
                    for i in Midx])
    spd = wsp[Midx]
    ym = eq[Midx]
    one = np.ones(len(Midx))
    d_oi = (lvl == "追い風").astype(float)
    d_mu = (lvl == "向かい風").astype(float)
    d_nw = (lvl == "無風").astype(float)
    bdefs = {
        "b1": (["intercept", "speed"], np.column_stack([one, spd])),
        "b2": (["intercept", "追い風", "向かい風", "無風"],
               np.column_stack([one, d_oi, d_mu, d_nw])),
        "b3": (["intercept", "追い風", "向かい風", "無風", "speed",
                "speed×追い風", "speed×向かい風"],
               np.column_stack([one, d_oi, d_mu, d_nw, spd,
                                spd * d_oi, spd * d_mu])),
    }
    b9 = {}
    for bname, (terms, X) in bdefs.items():
        beta, se, r2, nb = ols(X, ym)
        b9[bname] = {"n": nb, "R2": r2,
                     "coef": {t: {"est": float(b), "se": float(s)}
                              for t, b, s in zip(terms, beta, se)}}
    Xb3 = bdefs["b3"][1]
    Pb3 = np.linalg.inv(Xb3.T @ Xb3) @ Xb3.T

    # 作業5：直接検定（W0 風を統制しない / W1 eq から b3 予測値を引いた残差）
    rW1 = np.zeros(n)
    rW1[Midx] = ym - Xb3 @ (Pb3 @ ym)
    TW0 = pearson(eq[aW], eq[bW])
    TW1 = pearson(rW1[aW], rW1[bW])

    # ------------------------------------------------------------ 段階4・6の帰無
    # 帰無A：系列内で並べ替え。e と q に同じ置換を使う。
    rng = np.random.default_rng(SEED)
    sidf = sid.astype(float)
    nullA = np.empty(NREP)
    nullAd = {d: np.empty(NREP) for d in pairs}
    nullAq = np.empty(NREP)
    nullAeq = np.empty(NREP)
    nullAS = {s: np.empty(NREP) for s in spairs}
    nullAqd = {d: np.empty(NREP) for d in pairs}
    nullA8 = {key: np.empty(NREP) for key in c8}
    nullW0 = np.empty(NREP)
    nullW1 = np.empty(NREP)
    bufW1 = np.zeros(n)
    for k in range(NREP):
        perm = np.argsort(sidf + rng.random(n))
        ep = e[perm]
        qp = q[perm]
        eqp = eq[perm]
        for d, (aa, bb) in pairs.items():
            nullAd[d][k] = pearson(ep[aa], ep[bb])
        nullA[k] = nullAd[1][k]
        nullAq[k] = spearman(qp[a1], qp[b1])
        nullAeq[k] = pearson(eqp[a1], eqp[b1])
        for s, (aa, bb) in spairs.items():
            nullAS[s][k] = pearson(eqp[aa], eqp[bb])
        for d, (aa, bb) in pairs.items():
            nullAqd[d][k] = pearson(eqp[aa], eqp[bb])
        # 並べ替え後の系列に観測と同じ残差化をかけてから計算する
        resp = {"D0": eqp}
        for D in dprep:
            resp[D] = detrend(eqp, sid, nseries, *dprep[D])
        for key, v in c8.items():
            aa, bb = v["pairs"]
            nullA8[key][k] = pearson(resp[key[1]][aa], resp[key[1]][bb])
        # 段階9：並べ替え後の eq に観測と同じ b3 の当てはめ・残差化をかけてから計算する
        nullW0[k] = pearson(eqp[aW], eqp[bW])
        yk = eqp[Midx]
        bufW1[Midx] = yk - Xb3 @ (Pb3 @ yk)
        nullW1[k] = pearson(bufW1[aW], bufW1[bW])
        if (k + 1) % 100 == 0:
            print("帰無A %d/%d" % (k + 1, NREP))
    # 帰無B：(場,R)セル内で日をまたいで並べ替え。セル平均は不変なので p(場,R) はそのまま。
    rng = np.random.default_rng(SEED)
    cellf = cell.astype(float)
    base = np.argsort(cell, kind="stable")
    nullB = np.empty(NREP)
    nullBq = np.empty(NREP)
    nullBeq = np.empty(NREP)
    nullBS = {s: np.empty(NREP) for s in spairs}
    yp = np.empty(n)
    qp = np.empty(n, dtype=np.int64)
    for k in range(NREP):
        perm = np.argsort(cellf + rng.random(n))
        yp[base] = yf[perm]
        qp[base] = q[perm]
        ep = yp - pcell[cell]
        nullB[k] = pearson(ep[a1], ep[b1])
        nullBq[k] = spearman(qp[a1], qp[b1])
        eqp = qp - mqcell[cell]
        nullBeq[k] = pearson(eqp[a1], eqp[b1])
        for s, (aa, bb) in spairs.items():
            nullBS[s][k] = pearson(eqp[aa], eqp[bb])
        if (k + 1) % 100 == 0:
            print("帰無B %d/%d" % (k + 1, NREP))

    dA = describe(nullA, T3)
    dB = describe(nullB, T3)
    dAq = describe(nullAq, S_obs)
    dBq = describe(nullBq, S_obs)
    centerA = dA["mean"]
    T4 = T3 - centerA
    dAeq = describe(nullAeq, T3q)
    dBeq = describe(nullBeq, T3q)
    T4q = T3q - dAeq["mean"]
    st7sets = {}
    for s, (aa, bb) in spairs.items():
        dAs = describe(nullAS[s], T3qS[s])
        st7sets[s] = {
            "definition": SDEF[s],
            "nPairs": int(len(aa)),
            "T3q_cell": T3qS[s],
            "nullA_eq": dAs,
            "T4q_net": T3qS[s] - dAs["mean"],
            "pTwoSided": dAs["pTwoSided"],
            "nullB_q": describe(nullBS[s], T3qS[s]),
        }

    def transition(aa, bb):
        t = np.zeros((NQ, NQ), dtype=np.int64)
        np.add.at(t, (q[aa] - 1, q[bb] - 1), 1)
        return t
    trS = {s: transition(*spairs[s]) for s in ("S0", "S3")}

    st8cases = {}
    for (S, D), v in c8.items():
        dA8 = describe(nullA8[(S, D)], T8[(S, D)])
        st8cases["%s-%s" % (S, D)] = {
            "pairSet": S,
            "detrend": D,
            "nPairs": int(len(v["pairs"][0])),
            "excludedSeries": v["exSeries"],
            "excludedSeriesInPairSet": v["exSeriesInSet"],
            "excludedPairs": v["exPairs"],
            "T3q": T8[(S, D)],
            "nullA_eq": dA8,
            "net": T8[(S, D)] - dA8["mean"],
            "pTwoSided": dA8["pTwoSided"],
        }

    ref_resid = st8cases["S3-D1"]["net"]
    b3r = math.sqrt(b9["b3"]["R2"])
    med9 = {
        "b_b3_corr": b3r,
        "upper_speed": a9["speed"]["r"] * b3r ** 2,
        "upper_component": a9["component"]["r"] * b3r ** 2,
        "referenceResidual_S3D1net": ref_resid,
    }
    st9W = {}
    for wname, obs, nul in (("W0", TW0, nullW0), ("W1", TW1, nullW1)):
        dW = describe(nul, obs)
        st9W[wname] = {"nPairs": int(len(aW)), "T3q": obs, "nullA_eq": dW,
                       "net": obs - dW["mean"], "pTwoSided": dW["pTwoSided"]}
    underpowered = len(aW) < REQUIRED_PAIRS

    # ------------------------------------------------------------ 段階5
    cnt_s = np.bincount(sid, weights=yA)
    disp_rows = []
    num = den = 0.0
    for L in range(12, 0, -1):
        m = slen == L
        ns = int(m.sum())
        if ns == 0:
            continue
        c = cnt_s[m]
        mean = float(c.mean())
        var = float(c.var(ddof=1)) if ns >= 2 else float("nan")
        ph = mean / L
        ev = L * ph * (1 - ph)
        ratio = var / ev if ns >= 2 and ev > 0 else float("nan")
        if ns >= 2 and ev > 0:
            num += (ns - 1) * var
            den += (ns - 1) * ev
        disp_rows.append([L, ns, mean, var, ph, ev, ratio])
    pooled = num / den if den > 0 else float("nan")

    rateR = []
    for R in range(1, 13):
        m = rno == R
        rateR.append({"R": R, "n": int(m.sum()), "man": int(yA[m].sum()),
                      "rate": float(yA[m].mean())})
    rateV = []
    for i, v in enumerate(venues):
        m = ven == i
        rateV.append({"jcd": v, "n": int(m.sum()), "man": int(yA[m].sum()),
                      "rate": float(yA[m].mean())})

    # ------------------------------------------------------------ 段階6
    tr = np.zeros((NQ, NQ), dtype=np.int64)
    np.add.at(tr, (q[a1] - 1, q[b1] - 1), 1)

    # ------------------------------------------------------------ 書き出し
    finished = jst_now()
    summary = {
        "stage1": {
            "manRate": float(yA.mean()),
            "manCount": int(yA.sum()),
            "n": n,
            "quintileBounds": bounds,
            "quintileCounts": {str(i + 1): int(c) for i, c in enumerate(qcount)},
            "definition": "yA=1 if 3連単払戻>=10000。q=払戻の五分位（境界はソート後 ceil(k*n/5) 番目の額、同額は下位帯）",
        },
        "meta": {
            "script": "scripts/buildKensho05Flow.py",
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "runStartedJST": started.strftime("%Y-%m-%d %H:%M JST"),
            "runFinishedJST": finished.strftime("%Y-%m-%d %H:%M JST"),
            "seed": SEED,
            "reps": NREP,
            "input": "payrank/json（リポジトリ外・読み取りのみ）",
        },
        "stage0": {lab: cnt[k] for lab, k, _ in EXPECT},
        "stage2": {
            "seriesKey": "(開催日, 場)、系列内R昇順",
            "series": nseries,
            "seriesLenDist": lendist,
            "adjacentPairs": int(len(a1)),
            "breaks": breaks,
            "breaksDefinition": "同一系列で次の行とのR差が2以上に飛んだ箇所の数",
            "pairsByDistance": {str(d): int(len(pairs[d][0])) for d in pairs},
        },
        "stage3": {
            "statistic": "隣接ペア(R差=1)の Pearson 相関（ペア両側の標本平均で中心化する通常のPearson）",
            "T1_raw": T1,
            "T2_venueCentered": T2,
            "T3_cellCentered": T3,
            "T4_net": T4,
            "cells": 288,
            "decomposition": {
                "venueDiff_T1minusT2": T1 - T2,
                "rShape_T2minusT3": T2 - T3,
                "dayCommon_T3minusT4": T3 - T4,
            },
        },
        "stage4": {
            "nullA_center_shiftFromZero": centerA,
            "nullA_center_definition": "帰無A(系列内でeを並べ替え) 1000回の平均。ランダムでも偏って見える量",
            "nullA": dA,
            "nullB": dB,
            "nullB_definition": "(場,R)セル内で日をまたいでyAを並べ替え、T3と同じ中心化で再計算",
            "seedNote": "帰無A・帰無Bはそれぞれ default_rng(20260914) から開始。帰無Aは e と q に同じ置換を使う（帰無Bも yA と q に同じ置換）",
            "pValueDefinition": "min(1, 2*min((1+#null>=obs)/(1+B), (1+#null<=obs)/(1+B)))",
        },
        "stage5": {
            "dayCommon_overdispersionPooled": pooled,
            "dayCommon_definition": "系列ごとの荒れ本数の分散(ddof=1) ÷ 同じ系列長の二項分布の期待分散 L*p*(1-p)（p=その系列長群の荒れ率）。系列長別は dayDispersion.csv、pooled は (nSeries-1) 重み",
            "rShape_rateByR": rateR,
            "venueDiff_rateByVenue": rateV,
            "finiteSeriesBias_nullBCenter": dB["mean"],
            "finiteSeriesBiasNote": "帰無Bは日の共通要因を壊し(場,R)は保存するため、その中心が有限系列バイアス単独の量",
        },
        "stage6": {
            "statistic": "隣接ペアの q の Spearman 順位相関（中心化なし、同順位は平均順位）",
            "spearmanObserved": S_obs,
            "nullA_q": dAq,
            "nullB_q": dBq,
            "nullA_q_center_shiftFromZero": dAq["mean"],
            "transition": "quintileTransition.csv",
            "note": "yA版とq版のどちらを主にするかは判断しない",
        },
        "stage6b": {
            "statistic": "q を段階3と同じ手順で中心化した隣接ペアの Pearson 相関（eq = q - mean_q(場,R)、288セル）",
            "T1q_raw": T1q,
            "T2q_venue": T2q,
            "T3q_cell": T3q,
            "T4q_net": T4q,
            "cells": 288,
            "decomposition": {
                "venueDiff_T1qminusT2q": T1q - T2q,
                "rShape_T2qminusT3q": T2q - T3q,
                "dayCommon_T3qminusT4q": T3q - T4q,
            },
            "nullA_eq_center_shiftFromZero": dAeq["mean"],
            "nullA_eq": dAeq,
            "nullA_eq_definition": "各系列内で eq を並べ替えて T3q を再計算（帰無Aと同じ置換）",
            "nullB_q": dBeq,
            "nullB_q_definition": "(場,R)セル内で日をまたいで q を並べ替え、T3q と同じ中心化で再計算（帰無Bと同じ置換）",
            "note": "yA版とq版のどちらを主にするかは判断しない。Spearman版は stage6 に残す",
        },
        "stage7": {
            "setsuDefinition": "同一場で開催日を昇順に並べ、日付が1日ずつ連続する塊を1節とする。1日でも空いたら切る。開催日＝入力にその場の行がある日（全行が除外の場日も含む）",
            "setsuCount": len(setsu_lens),
            "setsuLenDist": lendist7(setsu_lens),
            "venueDaysAllExcluded": len(vdays) - nseries,
            "reference_setsuLenDist_adoptedDaysOnly": lendist7(setsu_lens_adopted),
            "reference_setsuCount_adoptedDaysOnly": len(setsu_lens_adopted),
            "seriesLastDay": int(s_last.sum()),
            "seriesPenultimateDay": int(s_pen.sum()),
            "seriesOther": int((~(s_last | s_pen)).sum()),
            "method": "中心化(eq)・統計量(Pearson)・帰無A_eq・帰無B_q は段階6bと同一（同じ置換）。ペア集合だけ差し替え。pTwoSided は帰無A_eq に対するもの",
            "sets": st7sets,
            "distanceCorrQ": "distanceCorrQ.csv",
            "transition": "quintileTransitionS3.csv（S0 と S3）",
        },
        "stage8": {
            "method": "中心化(eq)・ペア定義・統計量(Pearson)・帰無A_eq(1000回・seed 20260914・同じ置換)は段階6bと同一。系列(場×日)ごとに eq を R の多項式（切片つき）に回帰した残差で統計量を計算。帰無は系列内で eq を並べ替えた後に同じ回帰・残差化を行ってから計算",
            "detrendDefinition": {"D0": "トレンド除去なし", "D1": "R の1次式", "D2": "R の2次式"},
            "exclusion": "系列長が次数+2 に満たない系列は系列ごと除外（D1: 3本未満、D2: 4本未満）。excludedSeries は全体の除外系列数、excludedSeriesInPairSet はそのペア集合にペアを持っていた除外系列数、excludedPairs はそれで落ちたペア数",
            "pairSets": {"S0": SDEF["S0"], "S3": SDEF["S3"]},
            "cases": st8cases,
        },
        "stage9": {
            "method": "中心化(eq)・ペア定義(同一系列R差1)・統計量(Pearson)・帰無A_eq(1000回・seed 20260914・同じ置換)は段階6bと同一。ペア集合を突合できた行どうしに限定",
            "match": {
                "key": "開催日・場・R（results の 場コード文字列・レース'NR'文字列を変換して照合）",
                "resultsFiles": {"from": res_files[0], "to": res_files[1]},
                "windMissingDefinition": "風速が整数でない、または風向コードが1〜17の整数でない",
                "monthExclusion": "突合できたレースの風欠損率が10%を超える月を除外",
                "monthly": monthly,
                "excludedMonths": excluded_months,
                "period": {"start": mdates[0] if mdates else None,
                           "end": mdates[-1] if mdates else None},
                "matchedBeforeMonthExclusion": int(have.sum()),
                "matchedRaces": int(M.sum()),
                "resultsRacesInPeriod": len(in_period),
                "resultsRacesNotInAdopted": len(in_period - mkeys),
                "adjacentPairs": int(len(aW)),
            },
            "a": {
                "definition": "同一系列R差1ペアの隣接Pearson相関。各変数を(場,R)セル平均で中心化。風向角=(コード-1)×22.5。17=無風は sin/cos/水面成分で欠測（角度0として扱わない）。水面成分は追い風+1/横風0/向かい風-1（facts.md の判定式・stadiumBearing.json）",
                "vars": a9,
            },
            "b": {
                "definition": "突合できた行で eq を回帰（OLS・通常の標準誤差）。水面成分ダミーの基準は横風。b3 は 風速×水面成分の交互作用あり。無風は風速が常に0のため speed×無風 は恒等的に0で推定不能（列に入れない）",
                "models": b9,
            },
            "mediationUpper": dict(med9, definition="上限 = a × b²。a は作業2の風速・水面成分、b は b3 の √R²。比較対象は段階8 S3-D1 の net"),
            "W0": dict(st9W["W0"], definition="風を統制しない"),
            "W1": dict(st9W["W1"], definition="eq から b3 の予測値を引いた残差で計算。帰無は並べ替え後の eq に b3 を当てはめ直して残差化してから計算"),
            "underpowered": underpowered,
            "requiredPairs": REQUIRED_PAIRS,
        },
    }
    summary = roundtree(summary)

    crow = []
    for i, v in enumerate(venues):
        for R in range(1, 13):
            c = i * 12 + R - 1
            crow.append([v, R, int(ncell[c]), int(mcell[c]), float(pcell[c])])

    drow = []
    for d in pairs:
        s = describe(nullAd[d], Td[d])
        drow.append([d, int(len(pairs[d][0])), Td[d], s["mean"], s["sd"],
                     s["p2_5"], s["p97_5"], Td[d] - s["mean"], s["pTwoSided"]])

    qrow = []
    for i in range(NQ):
        rs = int(tr[i].sum())
        for j in range(NQ):
            qrow.append([i + 1, j + 1, int(tr[i, j]),
                         float(100.0 * tr[i, j] / rs) if rs else float("nan")])

    nrow = []
    for k in range(NREP):
        nrow.append([k + 1, float(nullA[k]), float(nullB[k]),
                     float(nullAq[k]), float(nullBq[k])]
                    + [float(nullAd[d][k]) for d in range(2, DMAX + 1)]
                    + [float(nullAeq[k]), float(nullBeq[k])])

    dqrow = []
    for d in pairs:
        s = describe(nullAqd[d], Tqd[d])
        dqrow.append([d, int(len(pairs[d][0])), Tqd[d], s["mean"], s["sd"],
                      s["p2_5"], s["p97_5"], Tqd[d] - s["mean"], s["pTwoSided"]])

    wmrow = []
    for name, v in a9.items():
        wmrow.append(["a", name, v["r"], None, v["nPairs"], "隣接Pearson・(場,R)中心化"])
    for bname, v in b9.items():
        for t, c in v["coef"].items():
            wmrow.append([bname, t, c["est"], c["se"], v["n"], "係数"])
        wmrow.append([bname, "R2", v["R2"], None, v["n"], "決定係数"])
    wmrow.append(["mediation", "b_b3_corr", med9["b_b3_corr"], None, None, "√R²(b3)"])
    wmrow.append(["mediation", "upper_speed", med9["upper_speed"], None, None, "a(風速)×b²"])
    wmrow.append(["mediation", "upper_component", med9["upper_component"], None, None,
                  "a(水面成分)×b²"])
    wmrow.append(["mediation", "referenceResidual_S3D1net", ref_resid, None, None,
                  "段階8 S3-D1 の net"])

    tsrow = []
    for s, t in trS.items():
        for i in range(NQ):
            rs = int(t[i].sum())
            for j in range(NQ):
                tsrow.append([s, i + 1, j + 1, int(t[i, j]),
                              float(100.0 * t[i, j] / rs) if rs else float("nan")])

    csvs = {
        "cellRates.csv":(["jcd", "R", "n", "man", "rate"], crow),
        "distanceCorr.csv": (["d", "nPairs", "residCorr", "nullA_center",
                              "nullA_sd", "nullA_p2_5", "nullA_p97_5", "net",
                              "pTwoSided"], drow),
        "dayDispersion.csv": (["seriesLen", "nSeries", "meanMan", "varMan",
                               "pHat", "expVarBinom", "overdispersionRatio"],
                              disp_rows),
        "quintileTransition.csv": (["fromQ", "toQ", "n", "rowPct"], qrow),
        "nullDist.csv": (["rep", "nullA_T", "nullB_T", "nullA_qSpearman",
                          "nullB_qSpearman"]
                         + ["nullA_T_d%d" % d for d in range(2, DMAX + 1)]
                         + ["nullA_eqT", "nullB_qT"], nrow),
        "distanceCorrQ.csv": (["d", "nPairs", "residCorrQ", "nullA_eq_center",
                               "nullA_eq_sd", "nullA_eq_p2_5",
                               "nullA_eq_p97_5", "net", "pTwoSided"], dqrow),
        "quintileTransitionS3.csv": (["set", "fromQ", "toQ", "n", "rowPct"],
                                     tsrow),
        "windMediation.csv": (["section", "name", "value", "se", "n", "note"],
                              wmrow),
    }

    # 既存出力の再現チェック：1つでも変わったら何も書かずに止まる
    diffs = check_repro(summary, csvs)
    # 段階7 S0 は段階6bの再掲。支給の期待値とも照合する
    s0 = summary["stage7"]["sets"]["S0"]
    b6 = summary["stage6b"]
    for label, got, exp in [
            ("stage7/S0/T3q_cell", s0["T3q_cell"], 0.028486),
            ("stage7/S0/nullA_eq/mean", s0["nullA_eq"]["mean"], 0.018992),
            ("stage7/S0/T3q_cell vs stage6b", s0["T3q_cell"], b6["T3q_cell"]),
            ("stage7/S0/T4q_net vs stage6b", s0["T4q_net"], b6["T4q_net"]),
            ("stage7/S0/nullA_eq vs stage6b", s0["nullA_eq"], b6["nullA_eq"]),
            ("stage7/S0/nullB_q vs stage6b", s0["nullB_q"], b6["nullB_q"]),
            ("distanceCorrQ d=1 vs stage6b", r6(Tqd[1]), b6["T3q_cell"]),
            ("quintileTransitionS3 S0 vs quintileTransition",
             trS["S0"].tolist(), tr.tolist()),
            ("stage8/S0-D0/T3q", summary["stage8"]["cases"]["S0-D0"]["T3q"],
             0.028486),
            ("stage8/S0-D0/nullA_eq/mean",
             summary["stage8"]["cases"]["S0-D0"]["nullA_eq"]["mean"], 0.018992),
            ("stage8/S0-D0/nullA_eq vs stage6b",
             summary["stage8"]["cases"]["S0-D0"]["nullA_eq"], b6["nullA_eq"]),
            ("stage8/S3-D0/T3q vs stage7 S3",
             summary["stage8"]["cases"]["S3-D0"]["T3q"],
             summary["stage7"]["sets"]["S3"]["T3q_cell"]),
            ("stage8/S3-D0/nullA_eq vs stage7 S3",
             summary["stage8"]["cases"]["S3-D0"]["nullA_eq"],
             summary["stage7"]["sets"]["S3"]["nullA_eq"])]:
        if got != exp:
            diffs.append((label, exp, got))
    if diffs:
        for path, old, new in diffs:
            print("REPRO NG: %s / 前 %s / 後 %s" % (path, old, new))
        stop("既存値が再現しない。何も書かない。")
    print("再現チェック OK")

    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "summary.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    for name, (header, rows_) in csvs.items():
        write_csv(os.path.join(OUTDIR, name), header, rows_)

    print("manRate=%.6f bounds=%s series=%d pairs=%d breaks=%d"
          % (yA.mean(), bounds, nseries, len(a1), breaks))
    print("T1=%.6f T2=%.6f T3=%.6f T4=%.6f" % (T1, T2, T3, T4))
    print("nullA mean=%.6f [%.6f, %.6f] p=%.4f / nullB mean=%.6f"
          % (dA["mean"], dA["p2_5"], dA["p97_5"], dA["pTwoSided"], dB["mean"]))
    print("Spearman=%.6f nullAq mean=%.6f nullBq mean=%.6f"
          % (S_obs, dAq["mean"], dBq["mean"]))
    print("T1q=%.6f T2q=%.6f T3q=%.6f T4q=%.6f" % (T1q, T2q, T3q, T4q))
    print("setsu=%d dist=%s" % (len(setsu_lens), lendist7(setsu_lens)))
    for s, v in st7sets.items():
        print("%s n=%d T3q=%.6f nullA=%.6f T4q=%.6f p=%.4f"
              % (s, v["nPairs"], v["T3q_cell"], v["nullA_eq"]["mean"],
                 v["T4q_net"], v["pTwoSided"]))
    print("stage9 matched=%d (before month excl %d) excluded=%s period=%s〜%s pairs=%d"
          % (M.sum(), have.sum(), excluded_months,
             mdates[0] if mdates else None, mdates[-1] if mdates else None, len(aW)))
    print("a: " + " / ".join("%s %.6f (n=%d)" % (k, v["r"], v["nPairs"])
                             for k, v in a9.items()))
    print("b R2: " + " / ".join("%s %.6f" % (k, v["R2"]) for k, v in b9.items()))
    print("upper speed %.8f / component %.8f / ref %.6f"
          % (med9["upper_speed"], med9["upper_component"], ref_resid))
    for wname, v in st9W.items():
        print("%s n=%d T3q=%.6f nullA=%.6f sd=%.6f net=%.6f p=%.4f"
              % (wname, v["nPairs"], v["T3q"], v["nullA_eq"]["mean"],
                 v["nullA_eq"]["sd"], v["net"], v["pTwoSided"]))
    print("underpowered=%s" % underpowered)
    for key, v in st8cases.items():
        print("%s n=%d exS=%d exSinSet=%d exP=%d T3q=%.6f nullA=%.6f net=%.6f p=%.4f"
              % (key, v["nPairs"], v["excludedSeries"],
                 v["excludedSeriesInPairSet"], v["excludedPairs"], v["T3q"],
                 v["nullA_eq"]["mean"], v["net"], v["pTwoSided"]))
    print("nullA_eq mean=%.6f [%.6f, %.6f] p=%.4f / nullB_q mean=%.6f p=%.4f"
          % (dAeq["mean"], dAeq["p2_5"], dAeq["p97_5"], dAeq["pTwoSided"],
             dBeq["mean"], dBeq["pTwoSided"]))


if __name__ == "__main__":
    main()
