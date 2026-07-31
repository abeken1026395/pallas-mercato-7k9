# -*- coding: utf-8 -*-
"""
E30燃料 影響検証 Phase 1
差分の差分法（stacked cohort DiD）／場クラスタ・ブートストラップ1000回

読み取り専用: kdata/racesAll.csv, kdata/entriesFull.csv, kdata/payouts*.csv,
              e30Schedule.json
書き込み先  : analysis/e30/ のみ（docs/ と kdata/ には一切書かない）
"""
import os, csv, json, glob, math
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTDIR = os.path.join(ROOT, "analysis", "e30")
RNG = np.random.default_rng(20260731)
NBOOT = 1000

# ---------------------------------------------------------------- 場の定義
# 処置群8場の切替日は e30Schedule.json から読む（ハードコードしない）
with open(os.path.join(ROOT, "e30Schedule.json"), encoding="utf-8") as f:
    SCHED = json.load(f)
SCHED_MAP = {v["jcd"]: v for v in SCHED["venues"]}

# データ開始(2025-07-15/kdataは250722)より前に切替済み → Phase1では完全除外
EXCLUDE_VENUES = {"11", "24"}          # びわこ・大村
TREAT = []                             # [(jcd, name, cut_hd6)]
for jcd, v in sorted(SCHED_MAP.items()):
    if jcd in EXCLUDE_VENUES:
        continue
    cut = v["startDate"].replace("-", "")[2:]   # YYYY-MM-DD -> YYMMDD
    TREAT.append((jcd, v["name"], cut))
TREAT_SET = {t[0] for t in TREAT}
ALL_VENUES = ["%02d" % i for i in range(1, 25)]
CONTROL = [j for j in ALL_VENUES if j not in TREAT_SET and j not in EXCLUDE_VENUES]

VENUE_NAME = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
    "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
    "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀",
    "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}

KIM_VALID = {"逃げ", "差し", "まくり", "まくり差し", "抜き", "恵まれ"}

# ---------------------------------------------------------------- 読み込み
def load():
    races = {}
    n_raw = 0
    kim_bad = []           # kimarite異常「ﾚｰｽﾀｲﾑ」
    for r in csv.DictReader(open(os.path.join(ROOT, "kdata/racesAll.csv"), encoding="utf-8")):
        n_raw += 1
        key = (r["hd"], r["jcd"], r["rno"])
        k = r["kimarite"].strip()
        if k not in KIM_VALID:
            kim_bad.append((key, k))
            continue
        races[key] = {"hd": r["hd"], "jcd": r["jcd"], "kimarite": k}

    # 3連単配当（不成立=payout空）
    tri, fusei = {}, []
    for f in sorted(glob.glob(os.path.join(ROOT, "kdata/payouts2*.csv"))):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r["shiki"] != "３連単":
                continue
            key = (r["hd"], r["jcd"], r["rno"])
            try:
                tri[key] = int(r["payout"])
            except ValueError:
                fusei.append((key, r["combo"]))

    # 中止・不成立、配当行なし を除外
    no_tri = [k for k in races if k not in tri]
    for k in no_tri:
        races.pop(k)
    for k, _ in fusei:
        races.pop(k, None)

    # entries（進入コース欠損は除外）
    ent_raw = 0
    shinnyu_missing = 0
    f_missing_shinnyu = 0
    agg = {}   # key -> dict(n_ent, n_F, inner1_win)
    for f in [os.path.join(ROOT, "kdata/entriesFull.csv")]:
        for r in csv.DictReader(open(f, encoding="utf-8")):
            ent_raw += 1
            key = (r["hd"], r["jcd"], r["rno"])
            sh = r["shinnyu"].strip()
            ch = r["chaku"].strip()
            if sh == "":
                shinnyu_missing += 1
                if ch == "F":
                    f_missing_shinnyu += 1
                continue
            if key not in races:
                continue
            a = agg.setdefault(key, {"n_ent": 0, "n_F": 0, "inner1": None})
            a["n_ent"] += 1
            if ch == "F":
                a["n_F"] += 1
            if sh == "1":
                a["inner1"] = 1 if ch == "01" else 0

    for key, a in agg.items():
        races[key].update(a)
        races[key]["pay"] = tri[key]

    # 進入1コース艇が特定できないレース（あれば除外）
    no_inner1 = [k for k, v in races.items() if v.get("inner1") is None]
    for k in no_inner1:
        races.pop(k)

    stats = {
        "raw_races": n_raw,
        "raw_entries": ent_raw,
        "excl_kimarite_racetime": len(kim_bad),
        "excl_no_trifecta": len(no_tri),
        "excl_fusei": len(fusei),
        "excl_no_inner1": len(no_inner1),
        "entries_shinnyu_missing": shinnyu_missing,
        "F_among_shinnyu_missing": f_missing_shinnyu,
        "kept_races": len(races),
    }
    return races, stats


RACES, CLEAN = load()

# ---------------------------------------------------------------- 集計器の事前計算
# 指標:
#  0 進入1コース1着率      = inner1win / n_races
#  1 逃げ比率              = nige / n_races
#  2 まくり+まくり差し比率  = mkr / n_races
#  3 差し比率              = sashi / n_races
#  4 3連単配当 中位数       (payout分布)
#  5 3連単配当 p75          (payout分布)
#  6 配当5000円以上比率     = ge5000 / n_races
#  7 出走1件あたりF率       = nF / n_entries
ACC = ["n_races", "inner1win", "nige", "mkr", "sashi", "ge5000", "n_ent", "nF"]
AI = {k: i for i, k in enumerate(ACC)}

V_IDX = {j: i for i, j in enumerate(ALL_VENUES)}
NCUT = len(TREAT)

pay_vals = np.array(sorted({r["pay"] for r in RACES.values()}), dtype=np.int64)
PB = {v: i for i, v in enumerate(pay_vals)}
NB = len(pay_vals)

# A[venue, cutoff, period, acc] / P[venue, cutoff, period, bin]
A = np.zeros((24, NCUT, 2, len(ACC)), dtype=np.float64)
P = np.zeros((24, NCUT, 2, NB), dtype=np.int32)

for r in RACES.values():
    vi = V_IDX[r["jcd"]]
    pb = PB[r["pay"]]
    k = r["kimarite"]
    for ci, (_, _, cut) in enumerate(TREAT):
        per = 1 if r["hd"] >= cut else 0
        a = A[vi, ci, per]
        a[AI["n_races"]] += 1
        a[AI["inner1win"]] += r["inner1"]
        a[AI["nige"]] += 1 if k == "逃げ" else 0
        a[AI["mkr"]] += 1 if k in ("まくり", "まくり差し") else 0
        a[AI["sashi"]] += 1 if k == "差し" else 0
        a[AI["ge5000"]] += 1 if r["pay"] >= 5000 else 0
        a[AI["n_ent"]] += r["n_ent"]
        a[AI["nF"]] += r["n_F"]
        P[vi, ci, per, pb] += 1


def wquantile(counts, p):
    """重み付き（度数）経験分位点。numpy既定(type-7)と同じ線形補間。"""
    N = counts.sum()
    if N == 0:
        return float("nan")
    cum = np.cumsum(counts)
    pos = p * (N - 1)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    frac = pos - lo
    i_lo = int(np.searchsorted(cum, lo + 1))
    i_hi = int(np.searchsorted(cum, hi + 1))
    return float(pay_vals[i_lo]) * (1 - frac) + float(pay_vals[i_hi]) * frac


def cell_metrics(acc, paycnt):
    """acc: 長さlen(ACC)の合計ベクトル / paycnt: bin度数 → 指標8つ"""
    nr = acc[AI["n_races"]]
    ne = acc[AI["n_ent"]]
    if nr == 0:
        return [float("nan")] * 8
    return [
        100.0 * acc[AI["inner1win"]] / nr,
        100.0 * acc[AI["nige"]] / nr,
        100.0 * acc[AI["mkr"]] / nr,
        100.0 * acc[AI["sashi"]] / nr,
        wquantile(paycnt, 0.50),
        wquantile(paycnt, 0.75),
        100.0 * acc[AI["ge5000"]] / nr,
        100.0 * acc[AI["nF"]] / ne if ne else float("nan"),
    ]


TREAT_VI = [V_IDX[t[0]] for t in TREAT]
CTRL_VI = [V_IDX[j] for j in CONTROL]


def estimate(treat_draw, ctrl_mult, cohorts=None):
    """treat_draw: 抽出されたコホート添字リスト（各要素は0..NCUT-1）
       ctrl_mult : 対照14場の重複度ベクトル(長さ14)
       戻り値: (DiD配列8, セル値dict)"""
    if cohorts is None:
        cohorts = list(range(NCUT))
    ws, cells = [], []
    for c in treat_draw:
        tvi = TREAT_VI[c]
        t_pre_a, t_post_a = A[tvi, c, 0], A[tvi, c, 1]
        t_pre_p, t_post_p = P[tvi, c, 0], P[tvi, c, 1]
        c_pre_a = np.tensordot(ctrl_mult, A[CTRL_VI, c, 0], axes=(0, 0))
        c_post_a = np.tensordot(ctrl_mult, A[CTRL_VI, c, 1], axes=(0, 0))
        c_pre_p = np.tensordot(ctrl_mult, P[CTRL_VI, c, 0], axes=(0, 0))
        c_post_p = np.tensordot(ctrl_mult, P[CTRL_VI, c, 1], axes=(0, 0))
        w = t_pre_a[AI["n_races"]] + t_post_a[AI["n_races"]]
        ws.append(w)
        cells.append((
            cell_metrics(t_pre_a, t_pre_p), cell_metrics(t_post_a, t_post_p),
            cell_metrics(c_pre_a, c_pre_p), cell_metrics(c_post_a, c_post_p),
        ))
    ws = np.array(ws, dtype=float)
    ws = ws / ws.sum()
    out = {}
    for i, nm in enumerate(["t_pre", "t_post", "c_pre", "c_post"]):
        out[nm] = np.array([sum(w * cl[i][m] for w, cl in zip(ws, cells)) for m in range(8)])
    did = (out["t_post"] - out["t_pre"]) - (out["c_post"] - out["c_pre"])
    return did, out


def run(cohort_idx, label):
    ctrl1 = np.ones(len(CONTROL))
    did, cells = estimate(cohort_idx, ctrl1)
    boots = np.zeros((NBOOT, 8))
    nT = len(cohort_idx)
    for b in range(NBOOT):
        td = [cohort_idx[i] for i in RNG.integers(0, nT, nT)]
        cd = RNG.integers(0, len(CONTROL), len(CONTROL))
        m = np.bincount(cd, minlength=len(CONTROL)).astype(float)
        boots[b], _ = estimate(td, m)
    lo = np.nanpercentile(boots, 2.5, axis=0)
    hi = np.nanpercentile(boots, 97.5, axis=0)
    return {"label": label, "did": did, "lo": lo, "hi": hi, "cells": cells,
            "cohorts": cohort_idx}


METRIC_NAMES = [
    "1 進入1コース艇の1着率(%)",
    "2 決まり手「逃げ」比率(%)",
    "3 まくり＋まくり差し比率(%)",
    "4 「差し」比率(%)",
    "5 3連単配当 中位数(円)",
    "6 3連単配当 75%点(円)",
    "7 3連単配当5000円以上の比率(%)",
    "8 出走1件あたりF発生率(%)",
]

if __name__ == "__main__":
    lines = []
    def w(s=""):
        lines.append(s)
        print(s)

    tot = CLEAN["raw_races"]
    excl = (CLEAN["excl_kimarite_racetime"] + CLEAN["excl_no_trifecta"]
            + CLEAN["excl_fusei"] + CLEAN["excl_no_inner1"])
    # 「ﾚｰｽﾀｲﾑ」10件と3連単なし10件は同一レース（重複計上を避ける）
    uniq_excl = tot - CLEAN["kept_races"]
    w("=== クリーニング ===")
    w("racesAll 生件数            : %d" % tot)
    w("除外 kimarite「ﾚｰｽﾀｲﾑ」     : %d" % CLEAN["excl_kimarite_racetime"])
    w("除外 3連単行なし            : %d （※上と同一レース）" % CLEAN["excl_no_trifecta"])
    w("除外 3連単「不成立」        : %d" % CLEAN["excl_fusei"])
    w("除外 進入1コース特定不可    : %d" % CLEAN["excl_no_inner1"])
    w("除外レース実数(重複排除)    : %d (%.3f%%)" % (uniq_excl, 100.0 * uniq_excl / tot))
    w("残レース                    : %d" % CLEAN["kept_races"])
    w("entries 生件数              : %d" % CLEAN["raw_entries"])
    w("除外 進入コース欠損(entry)  : %d （うちF: %d）"
      % (CLEAN["entries_shinnyu_missing"], CLEAN["F_among_shinnyu_missing"]))
    w()
    if 100.0 * uniq_excl / tot > 1.0:
        w("!!! 除外が1%%を超えたため分析を中止 !!!")
        raise SystemExit(1)

    hd_all = sorted({r["hd"] for r in RACES.values()})
    w("データ期間: %s 〜 %s" % (hd_all[0], hd_all[-1]))
    w()
    w("=== 群構成 ===")
    w("処置群8場: " + " / ".join("%s%s(切替%s)" % (j, n, c) for j, n, c in TREAT))
    w("対照群%d場: " % len(CONTROL) + " ".join("%s%s" % (j, VENUE_NAME[j]) for j in CONTROL))
    w("完全除外  : 11びわこ 24大村")
    w()

    res_all = run(list(range(NCUT)), "全8場")
    hei = [i for i, t in enumerate(TREAT) if t[0] == "04"][0]
    res_no_hei = run([i for i in range(NCUT) if i != hei], "平和島除く7場")

    for res in (res_all, res_no_hei):
        w("=" * 78)
        w("【%s】DiD推定量と95%%CI（場クラスタ・ブートストラップ%d回）" % (res["label"], NBOOT))
        w("=" * 78)
        c = res["cells"]
        for m in range(8):
            w(METRIC_NAMES[m])
            w("   処置群 前=%9.2f  後=%9.2f  差=%+9.2f" %
              (c["t_pre"][m], c["t_post"][m], c["t_post"][m] - c["t_pre"][m]))
            w("   対照群 前=%9.2f  後=%9.2f  差=%+9.2f" %
              (c["c_pre"][m], c["c_post"][m], c["c_post"][m] - c["c_pre"][m]))
            sig = "有意" if (res["lo"][m] > 0 or res["hi"][m] < 0) else "有意でない"
            w("   DiD = %+9.2f   95%%CI [%+9.2f, %+9.2f]   → %s"
              % (res["did"][m], res["lo"][m], res["hi"][m], sig))
            w()

    # セルn
    w("=" * 78)
    w("【各セルの n（レース数／出走数）】")
    w("=" * 78)
    for ci, (j, nm, cut) in enumerate(TREAT):
        vi = V_IDX[j]
        tp, ts = A[vi, ci, 0], A[vi, ci, 1]
        cp = A[CTRL_VI, ci, 0].sum(axis=0)
        cs = A[CTRL_VI, ci, 1].sum(axis=0)
        w("%s%s 切替%s : 処置前 %5d / 処置後 %5d レース  ｜ 対照前 %6d / 対照後 %6d レース"
          % (j, nm, cut, tp[AI["n_races"]], ts[AI["n_races"]],
             cp[AI["n_races"]], cs[AI["n_races"]]))
        w("            出走数: 処置前 %6d / 処置後 %6d ｜ 対照前 %6d / 対照後 %6d"
          % (tp[AI["n_ent"]], ts[AI["n_ent"]], cp[AI["n_ent"]], cs[AI["n_ent"]]))
    w()

    # 場別（参考）
    w("=" * 78)
    w("【参考】処置場ごとの DiD（n不足のため主結論にしない）")
    w("=" * 78)
    ctrl1 = np.ones(len(CONTROL))
    hdr = "場        " + "".join("%12s" % ("指標%d" % (m + 1)) for m in range(8))
    w(hdr)
    for ci, (j, nm, cut) in enumerate(TREAT):
        d, _ = estimate([ci], ctrl1)
        w("%s%-6s" % (j, nm) + "".join("%12.2f" % d[m] for m in range(8)))
    w()

    # 期間長
    w("=== 切替後の観測日数（kdata終端 %s まで） ===" % hd_all[-1])
    import datetime
    def d6(x):
        return datetime.date(2000 + int(x[:2]), int(x[2:4]), int(x[4:]))
    end = d6(hd_all[-1])
    for j, nm, cut in TREAT:
        w("  %s%-5s 切替%s → 後 %3d 日 / 前 %3d 日"
          % (j, nm, cut, (end - d6(cut)).days + 1, (d6(cut) - d6(hd_all[0])).days))

    with open(os.path.join(OUTDIR, "phase1_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
