#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""buildMae.py — 1マークの見立て（展示前版）を作る。docs/ichimark/index.html が読む（2026-11-01 けん裁定で実験場から本番へ）。

展示（スタート展示・展示タイム）が締切の約5分前にしか届かないため（2026-10-31 実測 n=38）、
展示を使わず、当日の朝に出ている材料だけで見立てる。

材料（すべてそのレースの前日までに分かっていたもの）
  出走表 … 級別・全国/当地の勝率系・F本数・平均ST・年齢・体重・モーター/ボート2連率・レースの格
  過去の結果 … 走数・直近180日のF本数・同じ場の直前6日の成績（節間）・過去1年のその枠からの成績・前づけの癖
  過去の直前情報 … ふだんのスタート展示ST・節の展示タイム偏差（前日まで）
1着の「コース×決まり手」15分類を LightGBM で出し、1逃げの確率をまとまりごとの厳密シャープレイ値で分ける。

出力（docs/ 配下はこの2つだけ。冪等：中身が同じなら書かない）
  docs/ichimark/mae_YYYYMMDD.json
  docs/ichimark/maeIndex.json
入力は読むだけ（results/・preview/・pv2/programs/ は書かない。当日の出走表は上流から取ってその場で使う）。

使い方:  python scripts/ichimark/buildMae.py [YYYYMMDD]   （省略時は JST の今日）
出走表がまだ無ければ何も書かずに終わる（終了コード0）。
"""
import bisect
import collections
import datetime
import glob
import gzip
import json
import math
import os
import sys
import urllib.request

import numpy as np
import lightgbm as lgb
from sklearn.metrics import log_loss

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTDIR = os.path.join(ROOT, "docs", "ichimark")
JST = datetime.timezone(datetime.timedelta(hours=9))
TRAIN_FROM = "20260101"
EVAL_FROM = "20260801"
VENUE = ["", "桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江",
         "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", "下関", "若松", "芦屋", "福岡", "唐津", "大村"]
CLS = {1: "A1", 2: "A2", 3: "B1", 4: "B2"}
GNAME = {1: "SG", 2: "G1", 3: "G2", 4: "G3", 5: "一般"}
NAN = float("nan")
PROG_KEYS = ["racer_national_top_1_percent", "racer_national_top_2_percent", "racer_local_top_1_percent",
             "racer_local_top_2_percent", "racer_flying_count", "racer_average_start_timing",
             "racer_assigned_boat_top_2_percent", "racer_age", "racer_weight"]
# 1艇あたりの列（この順で並べる）。分け方は SHAPLEY のまとまりに使う
BOAT_COLS = (["cls", "nr", "tenjiStAvg", "tenjiStN", "f180", "motor2"]
             + ["setsuN", "setsuCh", "setsuWin", "setsuTop2", "setsuSt", "setsuTenjiDev", "setsuTenjiSt"]
             + ["mzIn", "mzDiff", "mzOut", "mzN"]
             + ["wakuN", "wakuWin", "wakuTop2", "wakuSt"]
             + ["p_" + k for k in PROG_KEYS])
NB = len(BOAT_COLS)
SHINNYU = [BOAT_COLS.index(c) for c in ("mzIn", "mzDiff", "mzOut", "mzN")]
FCOL = [BOAT_COLS.index(c) for c in ("f180", "p_racer_flying_count")]
RACE0 = 3  # 先頭3列＝場（カテゴリ）・R番号・レースの格


def ymd(d, n):
    t = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])) - datetime.timedelta(n)
    return t.strftime("%Y%m%d")


def rno(s):
    return int(str(s).rstrip("R"))


def cls15(c, k):
    if k == "恵まれ":
        k = "抜き"
    if c == 1:
        return "1逃げ" if k == "逃げ" else "1その他"
    if c == 6:
        return "6〜"
    nm = {2: ["差し", "まくり"], 3: ["まくり", "まくり差し"], 4: ["まくり", "まくり差し"], 5: ["まくり差し", "まくり"]}[c]
    return "%d%s" % (c, k) if k in nm else "%dその他" % c


NAMES = sorted({cls15(c, k) for c in range(1, 7) for k in ("逃げ", "差し", "まくり", "まくり差し", "抜き", "恵まれ")})
NI = NAMES.index("1逃げ")
K = len(NAMES)


def load_json(p):
    try:
        if p.endswith(".gz"):
            return json.load(gzip.open(p))
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def fetch_program(hd):
    url = "https://raw.githubusercontent.com/BoatraceOpenAPI/programs/HEAD/docs/v2/%s/%s.json" % (hd[:4], hd)
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "data-seme/1.0"}), timeout=40).read()
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        print("programs miss", hd, e)
        return None


def prog_map(j):
    out = {}
    for p in (j or {}).get("programs", []):
        out[(int(p["race_stadium_number"]), int(p["race_number"]))] = p
    return out


# ---------------------------------------------------------------- 過去の素材
def load_history(hd):
    """hd より前の結果・直前情報を、選手ごとの出来事の列にする。"""
    ev = collections.defaultdict(list)
    races = []  # (日, 場, R, 結果)
    for f in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))):
        dd = os.path.basename(f)[:8]
        if dd >= hd:
            continue
        j = load_json(f)
        if not j:
            continue
        pv = {}
        pj = load_json(os.path.join(ROOT, "preview", dd + ".json")) or {}
        for p in pj.get("直前情報", []):
            rs = p.get("racers", [])
            ex = [x.get("exhibition_time") for x in rs if x.get("exhibition_time")]
            m = float(np.mean(ex)) if len(ex) >= 5 else None
            pv[(int(p["stadium_number"]), int(p["race_number"]))] = {
                x["entry_number"]: ((x["exhibition_time"] - m) if (m and x.get("exhibition_time")) else None,
                                    x.get("start_timing"), x.get("course_number")) for x in rs}
        for r in j.get("結果", []):
            v = int(r["場コード"]); rn = rno(r["レース"]); P = pv.get((v, rn), {})
            races.append((dd, v, rn, r, P))
            for b in r.get("艇", []):
                ch = b.get("着"); ch = ch if isinstance(ch, int) and 1 <= ch <= 6 else 6
                e = P.get(b["枠"], (None, None, None))
                st = b.get("ST")
                ev[b["登番"]].append((dd, v, rn, b["枠"], b.get("コース"), st if isinstance(st, (int, float)) else None,
                                     ch, e[0], e[1] if isinstance(e[1], (int, float)) else None))
    for t in ev:
        ev[t].sort()
    keys = {t: [x[0] for x in ev[t]] for t in ev}
    return ev, keys, races


def boat_feats(ev, keys, t, d, v, w, pb):
    """1艇ぶんの列（BOAT_COLS の順）。d より前の出来事だけを使う。"""
    out = [NAN] * NB
    out[0] = float(pb.get("racer_class_number") or NAN) if pb else NAN
    m2 = pb.get("racer_assigned_motor_top_2_percent") if pb else None
    out[5] = float(m2) if m2 else NAN
    for i, k in enumerate(PROG_KEYS):
        x = pb.get(k) if pb else None
        out[NB - len(PROG_KEYS) + i] = float(x) if x is not None else NAN
    if t not in ev:
        return out
    kt = keys[t]; L = ev[t]; i1 = bisect.bisect_left(kt, d)
    past = L[:i1]
    d180, d6, d365 = ymd(d, 180), ymd(d, 6), ymd(d, 365)
    out[1] = len(past)
    ts = [x[8] for x in past if x[8] is not None and x[8] >= 0]
    out[2] = float(np.mean(ts)) if ts else NAN
    out[3] = len(ts)
    out[4] = sum(1 for x in past if x[5] is not None and x[5] < 0 and x[0] >= d180)
    s = [x for x in L[bisect.bisect_left(kt, d6):i1] if x[1] == v]
    if s:
        sts = [x[5] for x in s if x[5] is not None]
        out[6:11] = [len(s), np.mean([x[6] for x in s]), np.mean([x[6] == 1 for x in s]),
                     np.mean([x[6] <= 2 for x in s]), float(np.mean(sts)) if sts else NAN]
        ex = [x[7] for x in s if x[7] is not None]
        es = [x[8] for x in s if x[8] is not None]
        out[11] = float(np.mean(ex)) if ex else NAN
        out[12] = float(np.mean(es)) if es else NAN
    h = [x for x in L[bisect.bisect_left(kt, d365):i1] if isinstance(x[4], int)]
    if h:
        out[13:17] = [np.mean([x[4] < x[3] for x in h]), np.mean([x[3] - x[4] for x in h]),
                      np.mean([x[4] > x[3] for x in h]), len(h)]
    a = [x for x in h if x[3] == w] if h else []
    if a:
        sa = [x[5] for x in a if x[5] is not None]
        out[17:21] = [len(a), np.mean([x[6] == 1 for x in a]), np.mean([x[6] <= 2 for x in a]),
                      float(np.mean(sa)) if sa else NAN]
    return out


def race_vec(ev, keys, d, v, rn, prog, toban):
    """toban: {枠: 登番}。prog: 出走表の1レース。"""
    pbs = {b["racer_boat_number"]: b for b in (prog or {}).get("boats", [])}
    g = (prog or {}).get("race_grade_number")
    vec = [float(v), float(rn), float(g) if g else NAN]
    for w in range(1, 7):
        vec += boat_feats(ev, keys, toban.get(w), d, v, w, pbs.get(w))
    return vec


def col(w, name):
    return RACE0 + (w - 1) * NB + BOAT_COLS.index(name)


def build_training(ev, keys, races):
    progs = {}
    X, y, meta = [], [], []
    for dd, v, rn, r, P in races:
        if dd < TRAIN_FROM:
            continue
        kim = r.get("決まり手")
        bs = {b["枠"]: b for b in r.get("艇", [])}
        if not kim or len(bs) != 6:
            continue
        wb = bs.get(r.get("1着"))
        if not wb or not isinstance(wb.get("コース"), int) or not 1 <= wb["コース"] <= 6:
            continue
        if dd not in progs:
            progs[dd] = prog_map(load_json(os.path.join(ROOT, "pv2", "programs", dd + ".json.gz")))
        pg = progs[dd].get((v, rn))
        if not pg:
            continue
        X.append(race_vec(ev, keys, dd, v, rn, pg, {w: b["登番"] for w, b in bs.items()}))
        y.append(NAMES.index(cls15(wb["コース"], kim)))
        meta.append((dd, v, rn, r, P))
    return np.array(X, float), np.array(y), meta


def fit(X, y):
    m = lgb.LGBMClassifier(objective="multiclass", n_estimators=250, learning_rate=0.03, num_leaves=4,
                           min_child_samples=200, reg_lambda=5, subsample=0.8, subsample_freq=1,
                           colsample_bytree=0.5, random_state=0, verbose=-1, n_jobs=2)
    return m.fit(X, y, categorical_feature=[0])


def proba(m, A):
    P = np.zeros((len(A), K))
    P[:, m.classes_] = m.predict_proba(A)
    return P


# ---------------------------------------------------------------- 答え合わせ・集計
def calib_bins(pn, isn):
    out = []
    for lo in range(0, 100, 10):
        s = (pn >= lo / 100) & (pn < (lo + 10) / 100)
        if s.sum():
            out.append({"bin": "%d-%d" % (lo, lo + 10), "n": int(s.sum()), "nige": round(float(isn[s].mean()), 3),
                        "meanPred": round(float(pn[s].mean()), 3)})
    return out


def evaluate(X, y, meta):
    d = np.array([m[0] for m in meta])
    tr = d < EVAL_FROM; te = ~tr
    if tr.sum() < 1000 or te.sum() < 1000:
        return None
    m = fit(X[tr], y[tr]); P = proba(m, X[te]); pn = P[:, NI]; yt = y[te]; isn = (yt == NI).astype(float)
    vt = X[:, 0].astype(int); c1 = X[:, col(1, "cls")]
    vr = {v: float((y[tr & (vt == v)] == NI).mean()) for v in set(vt[tr])}
    gm = float((y[tr] == NI).mean())
    pa = np.array([vr.get(v, gm) for v in vt[te]])
    kc = collections.defaultdict(lambda: [0, 0])
    for i in np.where(tr)[0]:
        q = kc[(vt[i], c1[i])]; q[0] += 1; q[1] += int(y[i] == NI)
    pb = np.array([(kc[(v, c)][1] + 20 * vr.get(v, gm)) / (kc[(v, c)][0] + 20) for v, c in zip(vt[te], c1[te])])

    def bm(p):
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return {"logloss": round(float(-np.mean(isn * np.log(p) + (1 - isn) * np.log(1 - p))), 4),
                "brier": round(float(np.mean((p - isn) ** 2)), 4)}
    g = X[te][:, 2]; cbg = {}
    for nm, gs in (("SG・G1", (1, 2)), ("G2・G3", (3, 4)), ("一般", (5,))):
        s = np.isin(g, gs)
        cbg[nm] = {"n": int(s.sum()), "nige": round(float(isn[s].mean()), 3) if s.sum() else None,
                   "calib": calib_bins(pn[s], isn[s])}
    last = max(d[te])
    span = "%d年%d月%d日から%d月%d日" % (int(EVAL_FROM[:4]), int(EVAL_FROM[4:6]), int(EVAL_FROM[6:]),
                                       int(last[4:6]), int(last[6:]))
    return {"calib": calib_bins(pn, isn),
            "eval": {"logloss": round(float(log_loss(yt, np.clip(P, 1e-9, 1), labels=range(K))), 4),
                     "brier": bm(pn)["brier"], "top1": round(float((P.argmax(1) == yt).mean()), 4),
                     "baseTop1": round(float(isn.mean()), 4), "nTrain": int(tr.sum()), "nEval": int(te.sum()),
                     "span": span, "compare": {"a_venueRate": bm(pa), "b_venue_x_c1cls": bm(pb), "c_model": bm(pn)},
                     "calibByGrade": cbg}}


def aggregates(races, hd):
    one = ymd(hd, 365)
    venue = collections.defaultdict(lambda: [0, 0]); sec = {}
    c1a = collections.defaultdict(lambda: [0, 0]); c1l = collections.defaultdict(lambda: [0, 0]); nat = [0, 0]
    st = {"to2": [0, 0], "waku": [0, 0], "c1taken": [0, 0]}; stall = [0, 0]; stv = {}
    for dd, v, rn, r, P in races:
        jc = "%02d" % v
        b = {x["枠"]: x for x in r.get("艇", [])}
        if dd >= one:
            for x in r.get("艇", []):
                if x.get("コース") == 1:
                    nat[0] += 1; nat[1] += int(x.get("着") == 1)
                    for dct, key in ((c1a, x["登番"]), (c1l, (jc, x["登番"]))):
                        dct[key][0] += 1; dct[key][1] += int(x.get("着") == 1)
        k = r.get("決まり手")
        if not k:
            continue
        w = b.get(r.get("1着")); s2 = b.get(r.get("2着")); s3 = b.get(r.get("3着"))
        if not w or not s2 or not w.get("コース") or not s2.get("コース"):
            continue
        for jj in ("all", jc):
            e = sec.setdefault(jj, {}).setdefault("%d%s" % (w["コース"], k), {"2": collections.Counter(), "3": collections.Counter()})
            e["2"][s2["コース"]] += 1
            if s3 and s3.get("コース"):
                e["3"][s3["コース"]] += 1
        if dd >= one:
            vv = venue[jc]; vv[1] += 1; vv[0] += int(w["コース"] == 1 and k == "逃げ")
        cm = {wk: x[2] for wk, x in P.items()}
        if len(cm) != 6 or set(cm.values()) != {1, 2, 3, 4, 5, 6}:
            continue
        n = int(w.get("コース") == 1 and k == "逃げ"); inv = {c: wk for wk, c in cm.items()}
        stall[0] += 1; stall[1] += n
        for key, cond in (("to2", inv[2] >= 3), ("waku", all(cm[x] == x for x in cm)), ("c1taken", inv[1] != 1)):
            if cond:
                st[key][0] += 1; st[key][1] += n
                q = stv.setdefault(jc, {"to2": [0, 0], "waku": [0, 0], "c1taken": [0, 0]})[key]; q[0] += 1; q[1] += n
    mz = {k: {"n": v[0], "nige": round(v[1] / v[0], 4)} for k, v in st.items() if v[0]}
    if stall[0]:
        mz["all"] = {"n": stall[0], "nige": round(stall[1] / stall[0], 4)}
    mz["byVenue"] = {jj: {kk: {"n": q[0], "nige": round(q[1] / q[0], 4)} for kk, q in dd.items() if q[0] >= 30}
                     for jj, dd in sorted(stv.items())}
    return ({j: {"rate": round(a / n, 4), "n": n} for j, (a, n) in sorted(venue.items())},
            {j: {k: {t: {str(c): n for c, n in sorted(v[t].items())} for t in v} for k, v in sorted(d_.items())}
             for j, d_ in sorted(sec.items())},
            mz, c1a, c1l, nat)


# ---------------------------------------------------------------- まとまりごとの寄与
def groups_of(vec):
    fs = {w: max([vec[col(w, "f180")] or 0, vec[col(w, "p_racer_flying_count")] or 0]) for w in range(1, 5)}
    G = collections.OrderedDict()
    for w in range(1, 7):
        base = RACE0 + (w - 1) * NB
        for o in range(NB):
            i = base + o
            if o in SHINNYU:
                G.setdefault("shinnyu", []).append(i)
            elif o in FCOL and w <= 4 and fs[w] >= 1:
                G.setdefault("f%d" % w, []).append(i)
            elif w <= 4:
                G.setdefault("p%d" % w, []).append(i)
            else:
                G.setdefault("c56", []).append(i)
    G["grade"] = [2]
    return G, fs


def shapley(m, vec, Xbg):
    G, fs = groups_of(vec)
    gn = list(G); nk = len(gn); f = np.array(vec, float)
    nb = len(Xbg); M = np.repeat(Xbg[None, :, :], 1 << nk, axis=0)
    M[:, :, 0] = f[0]; M[:, :, 1] = f[1]
    for S in range(1 << nk):
        for gi, g in enumerate(gn):
            if S >> gi & 1:
                M[S][:, G[g]] = f[G[g]]
    pn = proba(m, M.reshape(-1, M.shape[2]))[:, NI].reshape(1 << nk, nb).mean(1)
    fact = [math.factorial(q) for q in range(nk + 1)]
    phi = {}
    for gi, g in enumerate(gn):
        tot = 0.0
        for S in range(1 << nk):
            if S >> gi & 1:
                continue
            sz = bin(S).count("1")
            tot += fact[sz] * fact[nk - sz - 1] / fact[nk] * (pn[S | 1 << gi] - pn[S])
        phi[g] = tot
    assert abs(sum(phi.values()) - (pn[-1] - pn[0])) < 1e-9
    return float(pn[0]), phi, fs


def fmt(x, nd=0):
    return None if x is None or x != x else round(float(x), nd) if nd else int(round(float(x)))


# ---------------------------------------------------------------- 本体
def main():
    hd = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now(JST).strftime("%Y%m%d")
    prog = fetch_program(hd)
    pm = prog_map(prog)
    if not pm:
        print("出走表がまだありません", hd)
        return 0
    ev, keys, races = load_history(hd)
    X, y, meta = build_training(ev, keys, races)
    print("学習", len(X), "レース", flush=True)
    E = evaluate(X, y, meta)
    mdl = fit(X, y)
    venueNige, second, mz, c1a, c1l, nat = aggregates(races, hd)
    bgpool = collections.defaultdict(list)
    for i, m_ in enumerate(meta):
        bgpool[m_[1]].append(i)
    out = []
    for (v, rn), p in sorted(pm.items()):
        bs = {b["racer_boat_number"]: b for b in p.get("boats", [])}
        if len(bs) != 6:
            continue
        toban = {w: b.get("racer_number") for w, b in bs.items()}
        vec = race_vec(ev, keys, hd, v, rn, p, toban)
        P = proba(mdl, np.array([vec]))[0]; pn = float(P[NI])
        pool = bgpool.get(v) or list(range(len(X)))
        rng = np.random.RandomState(v * 100 + rn)
        Xbg = X[[pool[q] for q in rng.choice(len(pool), min(100, len(pool)), replace=False)]].copy()
        base, phi, fs = shapley(mdl, vec, Xbg)
        jc = "%02d" % v

        def b_(w, key):
            return vec[col(w, key)]

        def nm(w):
            return (bs[w].get("racer_name") or "").split()[0] if bs[w].get("racer_name") else "氏名不明"

        def who(w):
            c = CLS.get(bs[w].get("racer_class_number"), "級別不明")
            s = "%s・%s" % (c, nm(w))
            t2 = bs[w].get("racer_national_top_2_percent")
            if t2 is not None:
                s += "、全国2連率%d%%" % round(t2)
            m2 = bs[w].get("racer_assigned_motor_top_2_percent")
            if m2:
                s += "、機%d%%" % round(m2)
            n = b_(w, "setsuN")
            if n == n and n:
                s += "、今節%d走（1着%d）" % (n, round(b_(w, "setsuWin") * n))
            return s
        labels = {}
        for g in phi:
            if g == "p1":
                labels[g] = "1コースの選手の力：" + who(1)
            elif g[0] == "p":
                labels[g] = "%sコースの艇の力：%s" % (g[1], who(int(g[1])))
            elif g == "c56":
                labels[g] = "外：" + "／".join("%dコース %s・%s" % (w, CLS.get(bs[w].get("racer_class_number"), "-"), nm(w)) for w in (5, 6))
            elif g[0] == "f":
                labels[g] = "%sコース：F%d持ち" % (g[1], int(fs[int(g[1])]))
            elif g == "shinnyu":
                mzs = [w for w in range(2, 7) if b_(w, "mzN") >= 10 and b_(w, "mzIn") >= .2]
                labels[g] = "進入：" + ("、".join("%d号艇は過去1年 %d/%d走で枠より内へ" % (w, round(b_(w, "mzIn") * b_(w, "mzN")), b_(w, "mzN")) for w in mzs)
                                      if mzs else "前づけの多い選手はいない")
            else:
                gr = p.get("race_grade_number")
                labels[g] = "レースの格：" + (GNAME.get(int(gr), "不明") if gr else "不明")
        cand = sorted(({"key": g, "label": labels[g], "pt": round(phi[g] * 100, 1)} for g in phi), key=lambda x: -abs(x["pt"]))
        top = cand[:5]
        rest = round((pn - base) * 100 - sum(x["pt"] for x in top), 1)
        vg = round((base - venueNige[jc]["rate"]) * 100, 1) if jc in venueNige else None
        t1 = toban[1]; a = c1a.get(t1, [0, 0]); l = c1l.get((jc, t1), [0, 0])
        dl = (p.get("race_closed_at") or "")[11:16]
        boats = []
        for w in range(1, 7):
            b = bs[w]
            mzn = b_(w, "mzN")
            boats.append({"course": w, "waku": w, "toban": str(b.get("racer_number")), "name": nm(w),
                          "cls": CLS.get(b.get("racer_class_number"), ""), "motor": fmt(b.get("racer_assigned_motor_top_2_percent"), 2),
                          "fcount": int(b.get("racer_flying_count") or 0), "avgSt": fmt(b.get("racer_average_start_timing"), 2),
                          "nat2": fmt(b.get("racer_national_top_2_percent"), 1), "loc2": fmt(b.get("racer_local_top_2_percent"), 1),
                          "setsuN": fmt(b_(w, "setsuN")), "setsuWin": fmt(b_(w, "setsuWin") * b_(w, "setsuN")) if b_(w, "setsuN") == b_(w, "setsuN") else None,
                          "setsuCh": fmt(b_(w, "setsuCh"), 2),
                          "mz": [fmt(b_(w, "mzIn") * mzn), fmt(mzn)] if mzn == mzn and mzn else None})
            boats[-1] = {k_: v_ for k_, v_ in boats[-1].items() if v_ is not None}
        out.append({"jcd": jc, "rno": rn, "venue": VENUE[v], "pj": {NAMES[k]: round(float(P[k]), 3) for k in range(K)},
                    "base": round(base, 3), "venueGap": vg, "reasons": top, "rest": rest,
                    "c1": {"all": {"n": a[0], "w": a[1]}, "local": {"n": l[0], "w": l[1]},
                           "natRate": round(nat[1] / nat[0], 4) if nat[0] else None, "natN": nat[0]},
                    "boats": boats, "deadline": dl, "title": p.get("race_title") or "", "day": p.get("race_subtitle") or "",
                    "grade": GNAME.get(int(p["race_grade_number"]), "") if p.get("race_grade_number") else ""})
    doc = {"date": hd, "mode": "mae", "venueNige": venueNige, "second": second, "maezukeStats": mz, "races": out,
           "method": "展示前の材料だけで、LightGBM 15分類（1着のコース×決まり手）。学習 %s から前日まで %dレース。"
                     "寄与はまとまりごとの厳密シャープレイ値（背景＝同じ場の学習レースから無作為100件、場とR番号は固定）。"
                     "base＝背景の平均確率、rest＝(確率−base)×100−表示した上位5つの合計、venueGap＝(base−場の直近1年の逃げ率)×100。"
                     "図の進入は枠なりと仮定。" % (TRAIN_FROM, len(X))}
    if E:
        doc.update(E)
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, "mae_%s.json" % hd)
    body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != body:
        open(path, "w", encoding="utf-8").write(body)
        print("書いた", path, len(body.encode("utf-8")), "バイト", len(out), "レース")
    days = sorted(os.path.basename(f)[4:12] for f in glob.glob(os.path.join(OUTDIR, "mae_*.json")))
    ib = json.dumps({"days": days, "latest": days[-1]}, ensure_ascii=False, separators=(",", ":"))
    ip = os.path.join(OUTDIR, "maeIndex.json")
    if not os.path.exists(ip) or open(ip, encoding="utf-8").read() != ib:
        open(ip, "w", encoding="utf-8").write(ib)
    return 0


if __name__ == "__main__":
    sys.exit(main())
