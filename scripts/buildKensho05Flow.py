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
#   quintileTransitionS3.csv / … / conditionMediation.csv / conditionCourse1.csv
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


KIMARITE = ["逃げ", "差し", "まくり", "まくり差し", "抜き", "恵まれ"]
MIN_N11 = 300


def load_results_decision(dirpath, date_to):
    """results → {(開催日, 場コード'NN', R int): (K1, ①着外, 決まり手, 1着艇の本番コース)}。
    K1＝1号艇が1着か（1/0）。①着外は buildInSurvival.py と同一（1着〜3着が全て整数のとき
    3つの中に1が無ければ1）。揃わなければ K1・①着外とも None。決まり手はそのまま（統合しない）。"""
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
            key = (hd, jcd, int(str(r.get("レース"))[:-1]))
            top = [r.get("1着"), r.get("2着"), r.get("3着")]
            if all(is_int(x) for x in top):
                k1 = 1 if top[0] == 1 else 0
                o1 = 0 if 1 in top else 1
            else:
                k1 = o1 = None
            kim = r.get("決まり手")
            kim = kim if isinstance(kim, str) and kim else None
            wc = None
            if is_int(top[0]):
                for b in r.get("艇", []) or []:
                    if b.get("枠") == top[0] and is_int(b.get("コース")):
                        wc = b.get("コース")
            out[key] = (k1, o1, kim, wc)
    return out


# 段階13：results の実測条件（race レベルに実在するキーはこの6つ）
COND_ITEMS = ["風速", "風向コード", "波高", "気温", "水温", "天候コード"]


def cond_valid(name, v):
    """欠測でなければ True。風速・波高は0以上の整数、風向コードは1〜17の整数、
    天候コードは1〜6の整数、気温・水温は有限の数（整数または小数）。"""
    if name in ("風速", "波高"):
        return is_int(v) and v >= 0
    if name == "風向コード":
        return is_int(v) and 1 <= v <= 17
    if name == "天候コード":
        return is_int(v) and 1 <= v <= 6
    return (is_int(v) or isinstance(v, float)) and math.isfinite(v)


def load_results_conditions(dirpath, date_to):
    """results → {(開催日, 場コード'NN', R int): COND_ITEMS の値のタプル}。
    あわせて 2026-01-01 前後で race レベルの各キーが何レースに出現したかを数える。"""
    out = {}
    keys = {"pre": {}, "post": {}}
    races = {"pre": 0, "post": 0}
    names = sorted(n for n in os.listdir(dirpath)
                   if len(n) == 13 and n.endswith(".json") and n[:8].isdigit()
                   and n[:8] <= date_to)
    for name in names:
        hd = name[:8]
        per = "pre" if hd < "20260101" else "post"
        with open(os.path.join(dirpath, name), encoding="utf-8") as f:
            d = json.load(f)
        for r in d.get("結果", []) or []:
            races[per] += 1
            for k in r:
                keys[per][k] = keys[per].get(k, 0) + 1
            jcd = str(r.get("場コード", "")).zfill(2)
            key = (hd, jcd, int(str(r.get("レース"))[:-1]))
            out[key] = tuple(r.get(c) for c in COND_ITEMS)
    return out, keys, races


Z95 = 1.959963984540054
WEATHER = {1: "晴", 2: "曇", 3: "雨", 4: "雪", 6: "台風"}


def wilson(k, n):
    """buildKensho05Wind.py と同一の Wilson 95%。"""
    p = k / n
    den = 1 + Z95 * Z95 / n
    c = (p + Z95 * Z95 / (2 * n)) / den
    h = Z95 * math.sqrt(p * (1 - p) / n + Z95 * Z95 / (4 * n * n)) / den
    return c - h, c + h


def grouped_pearson(x, y, g, ng):
    """グループごとの Pearson 相関（g はペアのグループ番号）。"""
    n = np.bincount(g, minlength=ng).astype(float)
    sx = np.bincount(g, weights=x, minlength=ng)
    sy = np.bincount(g, weights=y, minlength=ng)
    sxx = np.bincount(g, weights=x * x, minlength=ng)
    syy = np.bincount(g, weights=y * y, minlength=ng)
    sxy = np.bincount(g, weights=x * y, minlength=ng)
    cov = sxy - sx * sy / n
    vx = sxx - sx * sx / n
    vy = syy - sy * sy / n
    return cov / np.sqrt(vx * vy)


def runs(y, seg_start):
    """y(bool) の最大連（区間の切れ目 seg_start をまたがない）の開始位置と長さ。"""
    prev_on = np.r_[False, y[:-1]] & ~seg_start
    next_on = np.r_[y[1:], False] & ~np.r_[seg_start[1:], True]
    si = np.flatnonzero(y & ~prev_on)
    ei = np.flatnonzero(y & ~next_on)
    return si, ei - si + 1


def runhist(y, seg_start):
    """最大連長ごとの件数（添字＝長さ、0〜12）。"""
    return np.bincount(runs(y, seg_start)[1], minlength=13)[:13]


def ks_uniform(p):
    """一様分布[0,1]に対する1標本 Kolmogorov–Smirnov。統計量Dと漸近p値。"""
    x = np.sort(p)
    n = len(x)
    i = np.arange(1, n + 1)
    d = float(max((i / n - x).max(), (x - (i - 1) / n).max()))
    lam = (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n)) * d
    j = np.arange(1, 201)
    pv = float(2 * np.sum((-1.0) ** (j - 1) * np.exp(-2 * j * j * lam * lam)))
    return d, min(1.0, max(0.0, pv))


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
           "stage6b", "stage7", "stage8", "stage9", "stage10"]
# 既存出力にあれば照合する（後から足した段階）
CHECKED_IF_PRESENT = ["stage11", "stage12", "stage13"]
# 後から足したCSV（既存出力に無ければ照合しない）
NEW_CSVS = {"distanceCorrQ.csv", "quintileTransitionS3.csv", "windMediation.csv",
            "streakCounts.csv", "extremeDays.csv", "decisionStreaks.csv",
            "venueBreakdown.csv", "conditionMediation.csv", "conditionCourse1.csv"}


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
        bj = json.load(f)["場"]
    bearing = {j: float(v["方位"]) for j, v in bj.items()}
    vnames = {j: v["場名"] for j, v in bj.items()}
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

    # 段階10 作業1：連続の回数（系列内でRが連続する区間のみ。重複を許さない最大連長）
    seg_start = np.r_[True, (sid[1:] != sid[:-1]) | (rno[1:] - rno[:-1] != 1)]
    yH = yA.astype(bool)
    yL = q == 1
    hH_obs = runhist(yH, seg_start)
    hL_obs = runhist(yL, seg_start)
    # 作業2：系列ごとの s＝隣接ペアの eq の積和
    s_obs = np.bincount(sid[a1], weights=eq[a1] * eq[b1], minlength=nseries)
    s_ge = np.zeros(nseries, dtype=np.int64)
    nullH = np.empty((NREP, len(hH_obs)))
    nullL = np.empty((NREP, len(hL_obs)))

    # 段階11：決まり方の流れ。段階9と同じ突合（M の行）だけを使い、その中で系列内並べ替え
    decmap = load_results_decision(RESULTS_DIR, RESULTS_TO)
    nU = len(Midx)
    usid = sid[Midx]
    urno = rno[Midx]
    ucell = cell[Midx]
    u_out = np.zeros(nU, dtype=bool)
    u_k1 = np.full(nU, np.nan)
    u_k3 = np.full(nU, np.nan)
    u_kim = np.full(nU, -1, dtype=np.int64)
    for j, i in enumerate(Midx):
        v = decmap.get((rows[i][0], rows[i][1], rows[i][2]))
        if v is None:
            stop("段階11: 突合済みのレースが results に無い: %s" % (rows[i][:3],))
        k1, o1, kim, wc = v
        if k1 is not None:
            u_k1[j] = k1
        if o1 is not None:
            u_out[j] = o1 == 1
        if kim is not None:
            if kim not in KIMARITE:
                stop("段階11: 想定外の決まり手 %r（統合せず停止）" % kim)
            u_kim[j] = KIMARITE.index(kim)
        if wc is not None:
            u_k3[j] = wc
    useg = np.r_[True, (usid[1:] != usid[:-1]) | (urno[1:] - urno[:-1] != 1)]
    upa = np.flatnonzero(~useg[1:])
    upb = upa + 1
    if len(upa) != len(aW):
        stop("段階11: 隣接ペア数が段階9と一致しない %d != %d" % (len(upa), len(aW)))

    def ucenter(x):
        ok = ~np.isnan(x)
        s = np.bincount(ucell[ok], weights=x[ok], minlength=len(ncell))
        c = np.bincount(ucell[ok], minlength=len(ncell))
        m = np.divide(s, c, out=np.zeros_like(s), where=c > 0)
        return x - m[ucell]
    u_k1c = ucenter(u_k1)
    u_k3c = ucenter(u_k3)

    def dec_stats(out_b, kim, k1c, k3c):
        hs = {"①着外": runhist(out_b, useg)}
        cat = []
        for ci, c in enumerate(KIMARITE):
            h = runhist(kim == ci, useg)
            hs["決まり手:" + c] = h
            cat.append(h)
        hs["決まり手:同一カテゴリ計"] = np.sum(cat, axis=0)
        ok = (kim[upa] >= 0) & (kim[upb] >= 0)
        match = float((kim[upa][ok] == kim[upb][ok]).mean())
        cr = {}
        for name, x in (("K1", k1c), ("K3", k3c)):
            m = ~np.isnan(x[upa]) & ~np.isnan(x[upb])
            cr[name] = (pearson(x[upa][m], x[upb][m]), int(m.sum()))
        return hs, (match, int(ok.sum())), cr
    obs11 = dec_stats(u_out, u_kim, u_k1c, u_k3c)
    n11hit = {"①着外": int(u_out.sum()),
              "決まり手:同一カテゴリ計": int((u_kim >= 0).sum())}
    for ci, c in enumerate(KIMARITE):
        n11hit["決まり手:" + c] = int((u_kim == ci).sum())
    rng11 = np.random.default_rng(SEED)
    usf = usid.astype(float)
    null11h = {key: np.empty((NREP, 13)) for key in obs11[0]}
    null11m = np.empty(NREP)
    null11c = {"K1": np.empty(NREP), "K3": np.empty(NREP)}
    for k in range(NREP):
        pu = np.argsort(usf + rng11.random(nU))
        hs, mt, cr = dec_stats(u_out[pu], u_kim[pu], u_k1c[pu], u_k3c[pu])
        for key, h in hs.items():
            null11h[key][k] = h
        null11m[k] = mt[0]
        for name in null11c:
            null11c[name][k] = cr[name][0]
    print("段階11 帰無 %d回 完了" % NREP)

    # 段階12：場別。段階6bの帰無A と同じ置換で場ごとの T3q と最安帯連続を数える
    NV = len(venues)
    gv = ven[a1]
    TV = grouped_pearson(eq[a1], eq[b1], gv, NV)
    v_series = np.bincount(ven[starts], minlength=NV)
    v_pairs = np.bincount(gv, minlength=NV)
    v_q1 = np.bincount(ven, weights=yL.astype(float), minlength=NV)
    siL0, lL0 = runs(yL, seg_start)
    LV_obs = np.bincount(ven[siL0] * 13 + lL0, minlength=NV * 13).reshape(NV, 13)
    nullV = np.empty((NREP, NV))
    nullLV = np.empty((NREP, NV, 13), dtype=np.int32)

    # 段階13 作業1：実測条件6項目の突合・月別欠損率（分母は段階9と同じ突合済みレース）
    condmap, ckeys, cnr = load_results_conditions(RESULTS_DIR, RESULTS_TO)
    cval = {c: np.full(n, np.nan) for c in COND_ITEMS}
    cmiss = {c: np.zeros(n, dtype=bool) for c in COND_ITEMS}
    cfrac = {c: np.zeros(n, dtype=bool) for c in COND_ITEMS}
    for i in np.flatnonzero(have):
        v = condmap.get(rows[i][:3])
        if v is None:
            stop("段階13: 突合済みのレースが results に無い: %s" % (rows[i][:3],))
        for c, x in zip(COND_ITEMS, v):
            if cond_valid(c, x):
                cval[c][i] = x
                cfrac[c][i] = isinstance(x, float) and x != int(x)
            else:
                cmiss[c][i] = True
    mon13 = {c: [] for c in COND_ITEMS}
    ex13 = {c: [] for c in COND_ITEMS}
    for mo in sorted(set(months[have].tolist())):
        mm = have & (months == mo)
        nm = int(mm.sum())
        for c in COND_ITEMS:
            k = int((cmiss[c] & mm).sum())
            mon13[c].append({"month": mo, "matched": nm, "missing": k,
                             "missingRate": k / nm})
            if k / nm > MISSING_MONTH_MAX:
                ex13[c].append(mo)
    M13 = M.copy()
    for c in COND_ITEMS:
        M13 &= ~cmiss[c] & ~np.isin(months, ex13[c])
    if not np.array_equal(M13, M):
        stop("段階13: 6項目の欠測・除外月で行集合が段階9と変わる（%d → %d）。"
             "W1 を段階9と同じ集合で再現できないため停止" % (M.sum(), M13.sum()))
    pre13 = np.array([t[0] < "20260101" for t in rows]) & have
    schema13 = {}
    for per, pm in (("before20260101", pre13), ("from20260101", have & ~pre13)):
        schema13[per] = {
            "resultsRaces": cnr["pre" if per == "before20260101" else "post"],
            "matched": int(pm.sum()),
            "items": {c: {"keyPresentInResults":
                          ckeys["pre" if per == "before20260101" else "post"].get(c, 0),
                          "missing": int((cmiss[c] & pm).sum()),
                          "fractionalValues": int((cfrac[c] & pm).sum())}
                      for c in COND_ITEMS}}
    wth = cval["天候コード"][Midx].astype(np.int64)
    wlev = sorted(set(wth.tolist()))
    if 1 not in wlev:
        stop("段階13: 天候コード1（晴）が無く基準水準が取れない")
    wdum = [(lv, (wth == lv).astype(float)) for lv in wlev if lv != 1]

    # 作業2：項目ごとの a と b²（段階9と同じ突合・ペア・(場,R)中心化）
    # a は「その項目で eq を回帰した当てはめ値」を(場,R)中心化した隣接Pearson。
    # 説明変数が1列の項目では項目そのものの a（段階9の定義）と一致する。
    nw13 = wcode[Midx] == 17
    sn13 = np.where(nw13, 0.0, np.sin(np.nan_to_num(ang[Midx])))
    cn13 = np.where(nw13, 0.0, np.cos(np.nan_to_num(ang[Midx])))
    allr = np.ones(len(Midx), dtype=bool)
    idefs = [
        ("風速", "風速(m)・連続量", allr, ["intercept", "speed"],
         np.column_stack([one, spd])),
        ("風向コード:角度", "風向角=(コード-1)×22.5 の sin・cos。17=無風は欠測（行ごと除く）",
         ~nw13, ["intercept", "sin", "cos"], np.column_stack([one, sn13, cn13])),
        ("風向コード:水面成分", "facts.md の判定式・stadiumBearing.json。横風基準のダミー（追い風/向かい風/無風）＝段階9 b2",
         allr, ["intercept", "追い風", "向かい風", "無風"],
         np.column_stack([one, d_oi, d_mu, d_nw])),
        ("波高", "波高(cm)・連続量", allr, ["intercept", "波高"],
         np.column_stack([one, cval["波高"][Midx]])),
        ("気温", "気温(℃)・連続量", allr, ["intercept", "気温"],
         np.column_stack([one, cval["気温"][Midx]])),
        ("水温", "水温(℃)・連続量", allr, ["intercept", "水温"],
         np.column_stack([one, cval["水温"][Midx]])),
        ("天候コード", "晴(1)基準のダミー（出現した水準 %s）" % wlev, allr,
         ["intercept"] + ["天候%d" % lv for lv, _ in wdum],
         np.column_stack([one] + [x for _, x in wdum])),
    ]
    item13 = {}
    for name, desc, rm, terms, X in idefs:
        beta, se, r2, nb = ols(X[rm], ym[rm])
        fit = np.full(n, np.nan)
        fit[Midx[rm]] = X[rm] @ beta
        fc = cell_center(fit)
        ok = ~np.isnan(fc[aW]) & ~np.isnan(fc[bW])
        a = pearson(fc[aW][ok], fc[bW][ok])
        item13[name] = {"definition": desc, "a": a, "aPairs": int(ok.sum()),
                        "b2_R2": r2, "n": nb, "upper": a * r2,
                        "coef": {t: {"est": float(b), "se": float(s)}
                                 for t, b, s in zip(terms, beta, se)}}

    # 作業3：6項目を同時に入れた統制（W7）。風の部分は段階9 b3 と同じ列
    t7 = (["intercept", "speed", "追い風", "向かい風", "無風", "speed×追い風",
           "speed×向かい風", "sin", "cos", "波高", "気温", "水温"]
          + ["天候%d" % lv for lv, _ in wdum])
    X7 = np.column_stack([one, spd, d_oi, d_mu, d_nw, spd * d_oi, spd * d_mu,
                          sn13, cn13, cval["波高"][Midx], cval["気温"][Midx],
                          cval["水温"][Midx]] + [x for _, x in wdum])
    beta7, se7, r2_7, n7 = ols(X7, ym)
    P7 = np.linalg.inv(X7.T @ X7) @ X7.T
    rW7 = np.zeros(n)
    rW7[Midx] = ym - X7 @ (P7 @ ym)
    TW7 = pearson(rW7[aW], rW7[bW])
    nullW7 = np.empty(NREP)
    bufW7 = np.zeros(n)

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
        # 段階13：同じ並べ替え後の eq に W7 の当てはめ・残差化をかけてから計算する
        bufW7[Midx] = yk - X7 @ (P7 @ yk)
        nullW7[k] = pearson(bufW7[aW], bufW7[bW])
        # 段階10：同じ系列内の置換で連続の回数と系列ごとの s を数える
        nullH[k] = runhist(yH[perm], seg_start)
        nullL[k] = runhist(qp == 1, seg_start)
        sk = np.bincount(sid[a1], weights=eqp[a1] * eqp[b1], minlength=nseries)
        s_ge += sk >= s_obs - 1e-12
        # 段階12：同じ置換で場ごとの T3q と最安帯の連続
        nullV[k] = grouped_pearson(eqp[a1], eqp[b1], gv, NV)
        siLk, lLk = runs(qp == 1, seg_start)
        nullLV[k] = np.bincount(ven[siLk] * 13 + lLk,
                                minlength=NV * 13).reshape(NV, 13)
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

    # 段階13 作業3 集計（W0・W1 は段階9と同じ観測・帰無の再掲）
    st13W = {}
    for wname, obs, nul in (("W0", TW0, nullW0), ("W1", TW1, nullW1),
                            ("W7", TW7, nullW7)):
        dW = describe(nul, obs)
        st13W[wname] = {"nPairs": int(len(aW)), "T3q": obs, "nullA_eq": dW,
                        "net": obs - dW["mean"], "pTwoSided": dW["pTwoSided"],
                        "insideNull95": bool(dW["p2_5"] <= obs <= dW["p97_5"])}

    # 段階13 作業4：①着外率を条件ごとに層別（①着外は段階11と同一、レースは段階9の突合済み）
    o4 = [decmap[rows[i][:3]][1] for i in Midx]
    v4 = np.array([x is not None for x in o4])
    i4 = Midx[v4]
    y4 = np.array([x for x in o4 if x is not None], dtype=float)
    j4 = ven[i4]
    c4 = np.bincount(j4, minlength=NV)
    pv4 = np.divide(np.bincount(j4, weights=y4, minlength=NV), c4,
                    out=np.zeros(NV), where=c4 > 0)
    r4 = y4 - pv4[j4]
    bands4 = []
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
        b = np.searchsorted(np.array(bq), x, side="left") + 1
        labs = ["<=%g" % bq[0], "%g<x<=%g" % (bq[0], bq[1]),
                "%g<x<=%g" % (bq[1], bq[2]), ">%g" % bq[2]]
        for j in range(4):
            bands4.append((c, "Q%d" % (j + 1), labs[j], b == j + 1))
    w4 = cval["天候コード"][i4].astype(np.int64)
    for lv in sorted(set(w4.tolist())):
        bands4.append(("天候コード", str(lv), WEATHER.get(lv, ""), w4 == lv))
    bands4.append(("全体", "計", "", np.ones(len(i4), dtype=bool)))
    ccrow = []
    for item, band, lab, m in bands4:
        nn = int(m.sum())
        kk = int(y4[m].sum())
        if nn >= MIN_N11:
            lo, hi = wilson(kk, nn)
            rr = r4[m]
            mr = float(rr.mean())
            h = Z95 * float(rr.std(ddof=1)) / math.sqrt(nn)
            ccrow.append([item, band, lab, nn, kk, round(100.0 * kk / nn, 2),
                          round(100.0 * lo, 2), round(100.0 * hi, 2),
                          round(100.0 * mr, 2) + 0.0, round(100.0 * (mr - h), 2) + 0.0,
                          round(100.0 * (mr + h), 2) + 0.0, ""])   # +0.0 で -0.0 を 0.0 に
        else:
            ccrow.append([item, band, lab, nn, kk, None, None, None, None, None,
                          None, "n不足"])

    # 段階10 集計
    def streak_table(h_obs, h_null):
        out = {}
        cols = [(str(k), h_obs[k], h_null[:, k]) for k in range(2, 7)]
        cols.append(("7+", h_obs[7:].sum(), h_null[:, 7:].sum(axis=1)))
        for label, ob, nu in cols:
            dsc = describe(nu.astype(float), float(ob))
            out[label] = {"observed": int(ob), "nullMean": dsc["mean"],
                          "nullSd": dsc["sd"], "p2_5": dsc["p2_5"],
                          "p97_5": dsc["p97_5"],
                          "ratio": float(ob) / dsc["mean"] if dsc["mean"] > 0 else None,
                          "pTwoSided": dsc["pTwoSided"]}
        return out
    st10H = streak_table(hH_obs, nullH)
    st10L = streak_table(hL_obs, nullL)
    p_series = (1 + s_ge) / (1 + NREP)
    ks_d, ks_p = ks_uniform(p_series)
    hist10 = np.histogram(p_series, bins=np.linspace(0, 1, 21))[0]
    npairs_series = np.bincount(sid[a1], minlength=nseries)
    # 作業3：p値の小さい順に上位50系列（同p値は s の大きい順）
    siH, lH = runs(yH, seg_start)
    siL, lL = runs(yL, seg_start)
    maxH = np.zeros(nseries, dtype=np.int64)
    maxL = np.zeros(nseries, dtype=np.int64)
    np.maximum.at(maxH, sid[siH], lH)
    np.maximum.at(maxL, sid[siL], lL)
    dvw = {}
    for (hd, jcd, _), (ms, _) in resmap.items():
        if is_int(ms):
            dvw.setdefault((hd, jcd), []).append(ms)
    # 段階11 集計
    def streak_n(h_obs, h_null, nhit):
        out = {}
        short = nhit < MIN_N11
        cols = [(str(k), h_obs[k], h_null[:, k]) for k in range(2, 7)]
        cols.append(("7+", h_obs[7:].sum(), h_null[:, 7:].sum(axis=1)))
        for label, ob, nu in cols:
            dsc = describe(nu.astype(float), float(ob))
            out[label] = {
                "observed": int(ob), "nullMean": dsc["mean"], "nullSd": dsc["sd"],
                "ratio": None if short or dsc["mean"] <= 0 else float(ob) / dsc["mean"],
                "pTwoSided": None if short else dsc["pTwoSided"],
                "note": "n不足" if short else ""}
        return out
    st11s = {key: {"n": n11hit[key],
                   "k": streak_n(obs11[0][key], null11h[key], n11hit[key])}
             for key in obs11[0]}
    dm = describe(null11m, obs11[1][0])
    m_short = obs11[1][1] < MIN_N11
    st11m = {"n": obs11[1][1], "observed": obs11[1][0], "nullMean": dm["mean"],
             "nullSd": dm["sd"],
             "ratio": None if m_short else obs11[1][0] / dm["mean"],
             "pTwoSided": None if m_short else dm["pTwoSided"],
             "note": "n不足" if m_short else ""}
    st11c = {}
    for name in ("K1", "K3"):
        ob, nn = obs11[2][name]
        dc = describe(null11c[name], ob)
        c_short = nn < MIN_N11
        st11c[name] = {"n": nn, "observed": ob, "nullA_center": dc["mean"],
                       "sd": dc["sd"], "p2_5": dc["p2_5"], "p97_5": dc["p97_5"],
                       "net": None if c_short else ob - dc["mean"],
                       "pTwoSided": None if c_short else dc["pTwoSided"],
                       "note": "n不足" if c_short else ""}

    # 段階12 集計
    centerV = nullV.mean(axis=0)
    st12v = []
    for v in range(NV):
        dv = describe(nullV[:, v], float(TV[v]))
        lk = {}
        short = v_q1[v] < MIN_N11
        for kk in range(2, 6):
            nu = nullLV[:, v, kk].astype(float)
            dl = describe(nu, float(LV_obs[v, kk]))
            lk[str(kk)] = {
                "observed": int(LV_obs[v, kk]), "nullMean": dl["mean"],
                "ratio": None if short or dl["mean"] <= 0
                else float(LV_obs[v, kk]) / dl["mean"],
                "pTwoSided": None if short else dl["pTwoSided"],
                "note": "n不足" if short else ""}
        st12v.append({
            "jcd": venues[v], "venue": vnames.get(venues[v], ""),
            "nSeries": int(v_series[v]), "nPairs": int(v_pairs[v]),
            "pairsPerRequired": int(v_pairs[v]) / REQUIRED_PAIRS,
            "underpowered": bool(v_pairs[v] < REQUIRED_PAIRS),
            "T3q": float(TV[v]), "nullA_eq": dv, "net": float(TV[v]) - dv["mean"],
            "sd": dv["sd"], "pTwoSided": dv["pTwoSided"],
            "nQ1": int(v_q1[v]), "lowestBandStreaks": lk})
    netV = TV - centerV
    obs_var = float(np.var(netV, ddof=1))
    null_var = np.var(nullV - centerV, axis=1, ddof=1)
    dvar = describe(null_var, obs_var)

    top = np.lexsort((-s_obs, p_series))[:50]
    exrow = []
    blank_before = blank_missing = 0
    for rank, s in enumerate(top, 1):
        i = starts[s]
        hd, jcd = rows[i][0], rows[i][1]
        ws = dvw.get((hd, jcd)) if hd >= res_files[0] else None
        if ws:
            wm, wr = sum(ws) / len(ws), max(ws) - min(ws)
            wn = len(ws)
        else:
            wm = wr = wn = None
            if hd < res_files[0]:
                blank_before += 1
            else:
                blank_missing += 1
        exrow.append([rank, hd, jcd, vnames.get(jcd, ""), int(slen[s]),
                      int(maxH[s]), int(maxL[s]), float(s_obs[s]),
                      float(p_series[s]),
                      None if wm is None else round(wm, 2), wr, wn])

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
        "stage10": {
            "streaks": {
                "definition": "系列(場×日)内でRが連続する区間だけを対象（欠番をまたいで繋がない）。重複を許さない最大連長方式：前後が途切れる最大の連を1件とし、その長さ k にだけ数える（長さ5の連は k=5 に1件、k=2〜4 には数えない）。H＝3連単払戻10,000円以上、L＝払戻の最安帯 q=1。長さ7以上は参考として 7+ にまとめる",
                "null": "各系列内で並べ替え（段階6bの帰無Aと同じ置換・1000回・seed 20260914）。系列をまたがない",
                "segments": int(seg_start.sum()),
                "H": st10H,
                "L": st10L,
                "file": "streakCounts.csv",
            },
            "seriesConcentration": {
                "definition": "系列ごとに s＝その系列の隣接ペア(R差1)の eq の積和（eq は段階6bと同一）。系列内並べ替え1000回（帰無Aと同じ置換）で片側p＝(1+#{s_null>=s})/(1+1000)。隣接ペアが無い系列は s=0 で p=1",
                "nSeries": nseries,
                "nSeriesNoPairs": int((npairs_series == 0).sum()),
                "ksStatistic": ks_d,
                "ksPValue": ks_p,
                "ksNote": "一様分布[0,1]に対する1標本KS（漸近p値）。p値は 1/1001 刻みの離散値",
                "nBelow05": int((p_series < 0.05).sum()),
                "shareBelow05": float((p_series < 0.05).mean()),
                "histogram005": [int(c) for c in hist10],
                "histogramNote": "0.05刻み20階級 [0,0.05),[0.05,0.10),…,[0.95,1.00]",
            },
            "extremeDays": {
                "file": "extremeDays.csv",
                "order": "p値の小さい順、同p値は s の大きい順に上位50系列",
                "wind": "results の同じ開催日・場の全レースの風速から平均と最大−最小。results の期間（%s〜）外、または該当レースが無い系列は空欄" % res_files[0],
                "windBlankBeforePeriod": blank_before,
                "windBlankMissingInPeriod": blank_missing,
            },
        },
        "stage11": {
            "definition": "段階9と同じ突合（results と開催日・場・Rで一致したレース）だけを使う。系列(場×日)・隣接ペア(R差1)・連続の数え方（重複を許さない最大連長、Rが連続する区間のみ）は段階6b・段階10と同一。帰無は突合済みレースの中で系列内並べ替え1000回（default_rng(20260914) から開始、場・系列をまたがない）",
            "vars": {
                "K1": "1号艇が1着か（1/0）。1着〜3着が全て整数のレースのみ",
                "①着外": "buildInSurvival.py と同一（1着〜3着が全て整数のとき、3つの中に1が無い）",
                "K2": "results の決まり手をそのまま（逃げ/差し/まくり/まくり差し/抜き/恵まれ）。統合しない。欠損は欠測（連続を切る・一致率の分母から除く）",
                "K3": "1着艇の本番進入コース（results の コース。展示進入は使わない）",
            },
            "races": nU,
            "adjacentPairs": int(len(upa)),
            "kimariteCounts": {c: n11hit["決まり手:" + c] for c in KIMARITE},
            "kimariteMissing": int((u_kim < 0).sum()),
            "nRule": "n が300未満のセルは比・net・pTwoSided を出さず note に n不足（n は表示）。連続の n はその事象が起きたレース数、一致率・相関の n は両側とも欠測でない隣接ペア数",
            "streaks": st11s,
            "streakNote": "H相当＝①着外の連続、L相当＝決まり手:逃げの連続。決まり手:同一カテゴリ計はカテゴリ別の連続件数の合計（同じ決まり手が続いた最大連の件数）",
            "matchRate": st11m,
            "corr": st11c,
            "corrDefinition": "K1・K3 を突合済みレースの(場,R)セル平均で中心化した残差の隣接Pearson相関。帰無は中心化済みの値を系列内で並べ替え",
            "file": "decisionStreaks.csv",
        },
        "stage12": {
            "definition": "10年534,330行・系列45,995・隣接ペア475,478。場ごとに段階6bと同一の T3q（eq の隣接Pearson）と帰無A_eq（段階6bと同じ置換1000回）。net＝T3q−帰無A_eq平均",
            "requiredPairs": REQUIRED_PAIRS,
            "venues": st12v,
            "betweenVenueVariance": dict(
                dvar,
                definition="24場の net の分散（ddof=1）。帰無は各置換回の24場の T3q から各場の帰無平均を引いた値の分散"),
            "lowestBandNote": "最安帯 q=1 の最大連長（段階10のLと同一）を場別に。n は場の q=1 レース数",
            "file": "venueBreakdown.csv",
        },
        "stage13": {
            "items": {
                "keys": COND_ITEMS,
                "note": "results の race レベルに実在する実測条件のキーは6つ（風速・風向コード・波高・気温・水温・天候コード）。指示の「7項目」の7つ目に当たるキーは無く、補わない。風向コードは 角度(sin・cos) と 水面成分 の2通りで表す",
            },
            "missing": {
                "definition": "風速・波高＝0以上の整数でない、風向コード＝1〜17の整数でない、天候コード＝1〜6の整数でない、気温・水温＝有限の数でない を欠測",
                "base": "段階9と同じ突合済みレース（開催日・場・R）",
                "monthExclusion": "項目ごとに月別欠損率が10%を超える月を除外",
                "monthly": mon13,
                "excludedMonths": ex13,
            },
            "schemaChange": dict(schema13, note="2026-01-01 前後で race レベルのキーの出現数・欠測数・小数値（整数でない値）の数を比較。keyPresentInResults は results 全体（〜%s）のレース数" % RESULTS_TO),
            "rows": {"races": int(M.sum()), "adjacentPairs": int(len(aW)),
                     "sameAsStage9": True},
            "mediation": {
                "definition": "中心化(eq, (場,R)288セル)・ペア(同一系列R差1)・突合は段階9と同一。b² は eq をその項目だけに回帰した R²（OLS）。a はその回帰の当てはめ値を(場,R)セル平均で中心化した隣接Pearson（説明変数が1列の項目では項目そのものの a と一致）。上限 = a × b²。比較対象は段階8 S3-D1 の net",
                "items": item13,
                "referenceResidual_S3D1net": ref_resid,
            },
            "control": {
                "method": "eq を W7 の説明変数に回帰（OLS）した残差で T3q を計算。統計量・ペア・帰無A_eq（系列内並べ替え1000回・default_rng(20260914)・段階6bと同じ置換）は段階6b・段階9と同一。帰無は並べ替え後の eq に同じ当てはめ・残差化をかけてから計算",
                "W7model": {"terms": t7, "n": n7, "R2": r2_7,
                            "coef": {t: {"est": float(b), "se": float(s)}
                                     for t, b, s in zip(t7, beta7, se7)},
                            "note": "風の部分は段階9 b3 と同じ列（横風基準）。sin・cos は無風(17)の行で0（無風ダミーが吸収するため角度としては欠測扱い）。天候は晴(1)基準のダミー"},
                "W0": dict(st13W["W0"], definition="統制なし（段階9 W0 の再掲）"),
                "W1": dict(st13W["W1"], definition="風だけ統制（段階9 W1 の再掲）"),
                "W7": dict(st13W["W7"], definition="実在する6項目すべてを統制（指示上の W7。7つ目の項目は results に無い）"),
                "insideNullDefinition": "帰無A_eq の 2.5〜97.5 パーセンタイルの内側に T3q がある（net 尺度では net が [p2_5−mean, p97_5−mean] の内側）",
            },
            "conditionCourse1": {
                "file": "conditionCourse1.csv",
                "sample": "段階9の突合済みレースのうち ①着外（段階11と同一）が判定できるもの",
                "races": int(len(i4)),
                "quartileBounds": qb4,
                "quartileRule": "ソート後 ceil(k*n/4) 番目の値を境界、同値は下位帯",
                "nRule": "n が300未満のセルは率・区間・残差を出さず note に n不足（n は表示）",
                "residual": "各レースの①着外(0/1)からその場の①着外率（同じ標本）を引いた残差の平均。区間は正規近似95%。単位は pt",
            },
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

    cmrow = []
    for name, v in item13.items():
        cmrow.append(["a", name, v["a"], None, v["aPairs"],
                      "当てはめ値の隣接Pearson・(場,R)中心化"])
        cmrow.append(["b2", name, v["b2_R2"], None, v["n"], "eq をその項目に回帰した R²"])
        cmrow.append(["upper", name, v["upper"], None, None, "a × b²"])
    for name in ("sin", "cos", "component"):
        cmrow.append(["aRef", name, a9[name]["r"], None, a9[name]["nPairs"],
                      "段階9 作業2 の a（項目そのもの）"])
    cmrow.append(["ref", "referenceResidual_S3D1net", ref_resid, None, None,
                  "段階8 S3-D1 の net"])
    for t, b, s in zip(t7, beta7, se7):
        cmrow.append(["W7coef", t, float(b), float(s), n7, "係数"])
    cmrow.append(["W7coef", "R2", r2_7, None, n7, "決定係数"])
    for wname, v in st13W.items():
        dW = v["nullA_eq"]
        for key, val in (("nPairs", v["nPairs"]), ("T3q", v["T3q"]),
                         ("nullMean", dW["mean"]), ("nullSd", dW["sd"]),
                         ("p2_5", dW["p2_5"]), ("p97_5", dW["p97_5"]),
                         ("net", v["net"]), ("pTwoSided", v["pTwoSided"]),
                         ("insideNull95", v["insideNull95"])):
            cmrow.append([wname, key, val, None, None, ""])

    dsrow = []
    for key, v in st11s.items():
        for kk, c in v["k"].items():
            dsrow.append(["streak", key, kk, v["n"], c["observed"], c["nullMean"],
                          c["nullSd"], c["ratio"], None, c["pTwoSided"], c["note"]])
    dsrow.append(["matchRate", "決まり手", None, st11m["n"], st11m["observed"],
                  st11m["nullMean"], st11m["nullSd"], st11m["ratio"], None,
                  st11m["pTwoSided"], st11m["note"]])
    for name, c in st11c.items():
        dsrow.append(["corr", name, None, c["n"], c["observed"], c["nullA_center"],
                      c["sd"], None, c["net"], c["pTwoSided"], c["note"]])

    vbrow = []
    for v in st12v:
        line = [v["jcd"], v["venue"], v["nSeries"], v["nPairs"],
                v["pairsPerRequired"], v["underpowered"], v["T3q"],
                v["nullA_eq"]["mean"], v["sd"], v["net"], v["pTwoSided"], v["nQ1"]]
        notes = set()
        for kk in range(2, 6):
            c = v["lowestBandStreaks"][str(kk)]
            line += [c["observed"], c["nullMean"], c["ratio"], c["pTwoSided"]]
            if c["note"]:
                notes.add(c["note"])
        vbrow.append(line + ["/".join(sorted(notes))])

    strow = []
    for typ, tab in (("H", st10H), ("L", st10L)):
        for kk, v in tab.items():
            strow.append([typ, kk, v["observed"], v["nullMean"], v["nullSd"],
                          v["p2_5"], v["p97_5"], v["ratio"], v["pTwoSided"]])

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
        "streakCounts.csv": (["type", "k", "observed", "nullMean", "nullSd",
                              "p2_5", "p97_5", "ratio", "pTwoSided"], strow),
        "extremeDays.csv": (["rank", "date", "jcd", "venue", "seriesLen",
                             "maxRunH", "maxRunL", "s", "p", "windMean",
                             "windRange", "windN"], exrow),
        "decisionStreaks.csv": (["section", "type", "k", "n", "observed",
                                 "nullMean", "nullSd", "ratio", "net",
                                 "pTwoSided", "note"], dsrow),
        "venueBreakdown.csv": (["jcd", "venue", "nSeries", "nPairs",
                                "pairsPerRequired", "underpowered", "T3q",
                                "nullA_eq_mean", "nullA_eq_sd", "net",
                                "pTwoSided", "nQ1"]
                               + ["L%d_%s" % (kk, c) for kk in range(2, 6)
                                  for c in ("obs", "nullMean", "ratio", "p")]
                               + ["note"], vbrow),
        "conditionMediation.csv": (["section", "name", "value", "se", "n", "note"],
                                   cmrow),
        "conditionCourse1.csv": (["item", "band", "range", "n", "out", "rate",
                                  "ciLow", "ciHigh", "residMeanPt",
                                  "residCiLowPt", "residCiHighPt", "note"], ccrow),
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
             summary["stage7"]["sets"]["S3"]["nullA_eq"])] + [
            ("stage13/control/%s/%s vs stage9" % (w, f),
             summary["stage13"]["control"][w][f], summary["stage9"][w][f])
            for w in ("W0", "W1")
            for f in ("nPairs", "T3q", "nullA_eq", "net", "pTwoSided")] + [
            ("stage13/control/W1/net", summary["stage13"]["control"]["W1"]["net"],
             0.00703),
            ("stage13 風速 a vs stage9 a speed",
             summary["stage13"]["mediation"]["items"]["風速"]["a"],
             summary["stage9"]["a"]["vars"]["speed"]["r"]),
            ("stage13 風速 b2 vs stage9 b1 R2",
             summary["stage13"]["mediation"]["items"]["風速"]["b2_R2"],
             summary["stage9"]["b"]["models"]["b1"]["R2"]),
            ("stage13 水面成分 b2 vs stage9 b2 R2",
             summary["stage13"]["mediation"]["items"]["風向コード:水面成分"]["b2_R2"],
             summary["stage9"]["b"]["models"]["b2"]["R2"]),
            ("stage13 角度 aPairs vs stage9 sin nPairs",
             summary["stage13"]["mediation"]["items"]["風向コード:角度"]["aPairs"],
             summary["stage9"]["a"]["vars"]["sin"]["nPairs"]),
            ("stage13 ref vs stage8 S3-D1 net",
             summary["stage13"]["mediation"]["referenceResidual_S3D1net"], 0.007496)]:
        if got != exp:
            diffs.append((label, exp, got))
    if diffs:
        for path, old, new in diffs:
            print("REPRO NG: %s / 前 %s / 後 %s" % (path, old, new))
        stop("既存値が再現しない。何も書かない。")
    print("再現チェック OK")

    os.makedirs(OUTDIR, exist_ok=True)
    # 段階14 は buildKensho05WindowB.py が書く。ここで再生成すると消えるので引き継ぐ
    sp = os.path.join(OUTDIR, "summary.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            prev = json.load(f)
        if "stage14" in prev:
            summary["stage14"] = prev["stage14"]
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
    for typ, tab in (("H", st10H), ("L", st10L)):
        print(typ + ": " + " / ".join(
            "k=%s obs %d null %.2f ratio %s p %.4f"
            % (kk, v["observed"], v["nullMean"],
               "%.3f" % v["ratio"] if v["ratio"] is not None else "-",
               v["pTwoSided"]) for kk, v in tab.items()))
    print("KS D=%.6f p=%.3g below05=%d (%.4f) noPairs=%d hist=%s"
          % (ks_d, ks_p, (p_series < 0.05).sum(), (p_series < 0.05).mean(),
             (npairs_series == 0).sum(), hist10.tolist()))
    print("top1 %s / blank before=%d missing=%d" % (exrow[0], blank_before, blank_missing))
    print("段階11 races=%d pairs=%d kim=%s missing=%d"
          % (nU, len(upa), {c: n11hit["決まり手:" + c] for c in KIMARITE},
             (u_kim < 0).sum()))
    for key in ("①着外", "決まり手:逃げ", "決まり手:同一カテゴリ計"):
        v = st11s[key]
        print("%s n=%d: " % (key, v["n"]) + " / ".join(
            "k=%s %d %.2f %s %s" % (kk, c["observed"], c["nullMean"],
                                   "%.3f" % c["ratio"] if c["ratio"] is not None else "-",
                                   "%.4f" % c["pTwoSided"] if c["pTwoSided"] is not None else c["note"])
            for kk, c in v["k"].items()))
    print("一致率 obs %.6f null %.6f ratio %.4f p %.4f n=%d"
          % (st11m["observed"], st11m["nullMean"], st11m["ratio"], st11m["pTwoSided"], st11m["n"]))
    for name, c in st11c.items():
        print("%s r=%.6f center=%.6f sd=%.6f net=%.6f p=%.4f n=%d"
              % (name, c["observed"], c["nullA_center"], c["sd"], c["net"], c["pTwoSided"], c["n"]))
    for v in sorted(st12v, key=lambda v: -v["net"]):
        l5 = v["lowestBandStreaks"]["5"]
        print("%s %s net=%.6f pairs=%d p=%.4f under=%s L5 %d/%.2f/%s"
              % (v["jcd"], v["venue"], v["net"], v["nPairs"], v["pTwoSided"],
                 v["underpowered"], l5["observed"], l5["nullMean"],
                 "%.3f" % l5["ratio"] if l5["ratio"] is not None else l5["note"]))
    print("場間分散 obs %.3e null %.3e [%.3e, %.3e] p=%.4f"
          % (dvar["observed"], dvar["mean"], dvar["p2_5"], dvar["p97_5"], dvar["pTwoSided"]))
    print("段階13 除外月 %s / 欠測 %s" % (ex13, {c: int(cmiss[c].sum()) for c in COND_ITEMS}))
    for name, v in item13.items():
        print("段階13 %s a=%.6f (n=%d) b2=%.6f upper=%.8f"
              % (name, v["a"], v["aPairs"], v["b2_R2"], v["upper"]))
    for wname, v in st13W.items():
        print("段階13 %s n=%d T3q=%.6f nullA=%.6f sd=%.6f [%.6f, %.6f] net=%.6f p=%.4f inside=%s"
              % (wname, v["nPairs"], v["T3q"], v["nullA_eq"]["mean"],
                 v["nullA_eq"]["sd"], v["nullA_eq"]["p2_5"], v["nullA_eq"]["p97_5"],
                 v["net"], v["pTwoSided"], v["insideNull95"]))
    print("段階13 W7 R2=%.6f n=%d / 作業4 races=%d n不足=%d"
          % (r2_7, n7, len(i4), sum(1 for r in ccrow if r[-1] == "n不足")))
    for r in ccrow:
        print("作業4 " + " ".join(str(x) for x in r))
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
