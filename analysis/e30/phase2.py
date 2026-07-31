# -*- coding: utf-8 -*-
"""
E30燃料 影響検証 Phase 2
outcome を「予想精度」に差し替えた stacked cohort DiD。
群構成・切替日・CI手法は Phase 1 と完全に同一。

読み取り専用: verify_log.csv, e30Schedule.json
書き込み先  : analysis/e30/ のみ
"""
import os, csv, json, math
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTDIR = os.path.join(ROOT, "analysis", "e30")
RNG = np.random.default_rng(20260801)
NBOOT = 1000
NBLOCK = 8          # 事前トレンド用: 切替前の30日ブロック数

# ---------------------------------------------------------------- 群の定義（Phase 1 と同一）
with open(os.path.join(ROOT, "e30Schedule.json"), encoding="utf-8") as f:
    SCHED = json.load(f)
EXCLUDE_VENUES = {"11", "24"}
TREAT = []
for v in sorted(SCHED["venues"], key=lambda x: x["jcd"]):
    if v["jcd"] in EXCLUDE_VENUES:
        continue
    TREAT.append((v["jcd"], v["name"], v["startDate"].replace("-", "")))   # YYYYMMDD
TREAT_SET = {t[0] for t in TREAT}
ALL_VENUES = ["%02d" % i for i in range(1, 25)]
CONTROL = [j for j in ALL_VENUES if j not in TREAT_SET and j not in EXCLUDE_VENUES]
V_IDX = {j: i for i, j in enumerate(ALL_VENUES)}
NCUT = len(TREAT)
TREAT_VI = [V_IDX[t[0]] for t in TREAT]
CTRL_VI = [V_IDX[j] for j in CONTROL]

VENUE_NAME = {"01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
              "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
              "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀",
              "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
              "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村"}

import datetime
def d8(x):
    return datetime.date(int(x[:4]), int(x[4:6]), int(x[6:]))

# ---------------------------------------------------------------- 読み込み
def load():
    rows, bad = [], {"score": 0, "chaku": 0, "shuyaku": 0, "hairan_mark": 0}
    n_raw = 0
    for r in csv.DictReader(open(os.path.join(ROOT, "verify_log.csv"), encoding="utf-8-sig")):
        n_raw += 1
        try:
            sc = float(r["スコア"])
        except ValueError:
            bad["score"] += 1
            continue
        f = r["着順"].split("-")
        if len(f) != 3:
            bad["chaku"] += 1
            continue
        if r["主役正誤"] not in ("◎", "○", "×"):
            bad["shuyaku"] += 1
            continue
        if r["波乱正誤"] not in ("○", "×", "-"):
            bad["hairan_mark"] += 1
            continue
        rows.append({
            "hd": r["日付"], "jcd": r["場コード"], "hantei": r["判定"],
            "score": sc, "maru": 1 if r["主役正誤"] == "◎" else 0,
            "top3": 1 if r["主役正誤"] in ("◎", "○") else 0,
            "judged": 0 if r["判定"] == "混戦" else 1,
            "hit": 1 if r["波乱正誤"] == "○" else 0,
        })
    return rows, n_raw, bad


ROWS, N_RAW, BAD = load()
SCORES = np.array(sorted({r["score"] for r in ROWS}))
SB = {s: i for i, s in enumerate(SCORES)}
NS = len(SCORES)

# ---------------------------------------------------------------- 集計器
ACC = ["n", "maru", "top3", "judged", "hit",
       "katame", "katame_hit", "haran", "haran_hit"]
AI = {k: i for i, k in enumerate(ACC)}
NA = len(ACC)

# period: 0=前, 1=後 / block: 0..NBLOCK-1 は切替前の30日ブロック(-NBLOCK..-1)
A = np.zeros((24, NCUT, 2, NA))
POS = np.zeros((24, NCUT, 2, NS))     # ◎=1 のスコア度数
NEG = np.zeros((24, NCUT, 2, NS))     # ◎=0 のスコア度数
AB = np.zeros((24, NCUT, NBLOCK, NA))
POSB = np.zeros((24, NCUT, NBLOCK, NS))
NEGB = np.zeros((24, NCUT, NBLOCK, NS))

CUT_D = [d8(t[2]) for t in TREAT]
for r in ROWS:
    vi = V_IDX[r["jcd"]]
    sb = SB[r["score"]]
    d = d8(r["hd"])
    for ci in range(NCUT):
        delta = (d - CUT_D[ci]).days
        per = 1 if delta >= 0 else 0
        for arr, pos, neg, idx in ((A, POS, NEG, per),):
            a = arr[vi, ci, idx]
            a[AI["n"]] += 1
            a[AI["maru"]] += r["maru"]
            a[AI["top3"]] += r["top3"]
            a[AI["judged"]] += r["judged"]
            a[AI["hit"]] += r["hit"] if r["judged"] else 0
            if r["hantei"] == "堅め":
                a[AI["katame"]] += 1
                a[AI["katame_hit"]] += r["hit"]
            elif r["hantei"] == "波乱":
                a[AI["haran"]] += 1
                a[AI["haran_hit"]] += r["hit"]
            (pos if r["maru"] else neg)[vi, ci, idx, sb] += 1
        # 事前トレンド用ブロック（切替直前30日 = block index NBLOCK-1）
        if delta < 0:
            bi = NBLOCK - 1 - ((-delta - 1) // 30)
            if 0 <= bi < NBLOCK:
                a = AB[vi, ci, bi]
                a[AI["n"]] += 1
                a[AI["maru"]] += r["maru"]
                a[AI["top3"]] += r["top3"]
                a[AI["judged"]] += r["judged"]
                a[AI["hit"]] += r["hit"] if r["judged"] else 0
                if r["hantei"] == "堅め":
                    a[AI["katame"]] += 1
                    a[AI["katame_hit"]] += r["hit"]
                elif r["hantei"] == "波乱":
                    a[AI["haran"]] += 1
                    a[AI["haran_hit"]] += r["hit"]
                (POSB if r["maru"] else NEGB)[vi, ci, bi, sb] += 1


def auc_from_counts(pos, neg):
    """タイ補正込みのAUC（Mann-Whitney）。pos/neg はスコアbin度数。"""
    P, N = pos.sum(), neg.sum()
    if P == 0 or N == 0:
        return float("nan")
    cum_neg_below = np.concatenate(([0.0], np.cumsum(neg)[:-1]))
    return float((pos * (cum_neg_below + 0.5 * neg)).sum() / (P * N))


NM = 6
METRIC_NAMES = [
    "1  主役正誤 的中率＝◎率(1着的中, %)",
    "1s 主役正誤 3着以内率(◎+○, %)  ※補助",
    "2  波乱正誤 的中率(混戦除く, %)",
    "3  スコアのAUC（◎=主役艇1着 を判別）",
    "4a 判定「堅め」の的中率(%)",
    "4b 判定「波乱」の的中率(%)",
]


def cell(acc, pos, neg):
    n, j = acc[AI["n"]], acc[AI["judged"]]
    k, h = acc[AI["katame"]], acc[AI["haran"]]
    return [
        100.0 * acc[AI["maru"]] / n if n else float("nan"),
        100.0 * acc[AI["top3"]] / n if n else float("nan"),
        100.0 * acc[AI["hit"]] / j if j else float("nan"),
        auc_from_counts(pos, neg),
        100.0 * acc[AI["katame_hit"]] / k if k else float("nan"),
        100.0 * acc[AI["haran_hit"]] / h if h else float("nan"),
    ]


def estimate(treat_draw, cm, wmode="total"):
    """wmode='total': 処置場の全行数で加重（既定・Phase 1 と同じ）
       wmode='post' : 切替後の行数で加重（切替後が短い場の影響を抑える感度分析）"""
    ws, cells = [], []
    for c in treat_draw:
        tvi = TREAT_VI[c]
        tp = cell(A[tvi, c, 0], POS[tvi, c, 0], NEG[tvi, c, 0])
        ts = cell(A[tvi, c, 1], POS[tvi, c, 1], NEG[tvi, c, 1])
        cp = cell(np.tensordot(cm, A[CTRL_VI, c, 0], axes=(0, 0)),
                  np.tensordot(cm, POS[CTRL_VI, c, 0], axes=(0, 0)),
                  np.tensordot(cm, NEG[CTRL_VI, c, 0], axes=(0, 0)))
        cs = cell(np.tensordot(cm, A[CTRL_VI, c, 1], axes=(0, 0)),
                  np.tensordot(cm, POS[CTRL_VI, c, 1], axes=(0, 0)),
                  np.tensordot(cm, NEG[CTRL_VI, c, 1], axes=(0, 0)))
        ws.append(A[tvi, c, 1][AI["n"]] if wmode == "post"
                  else A[tvi, c, 0][AI["n"]] + A[tvi, c, 1][AI["n"]])
        cells.append((tp, ts, cp, cs))
    ws = np.array(ws) / np.sum(ws)
    out = {}
    for i, nm in enumerate(["t_pre", "t_post", "c_pre", "c_post"]):
        out[nm] = np.array([sum(w * cl[i][m] for w, cl in zip(ws, cells)) for m in range(NM)])
    return (out["t_post"] - out["t_pre"]) - (out["c_post"] - out["c_pre"]), out


def run(cohorts, label, wmode="total"):
    one = np.ones(len(CONTROL))
    did, cells = estimate(cohorts, one, wmode)
    boots = np.zeros((NBOOT, NM))
    nT = len(cohorts)
    for b in range(NBOOT):
        td = [cohorts[i] for i in RNG.integers(0, nT, nT)]
        cm = np.bincount(RNG.integers(0, len(CONTROL), len(CONTROL)),
                         minlength=len(CONTROL)).astype(float)
        boots[b], _ = estimate(td, cm, wmode)
    return {"label": label, "did": did, "cells": cells,
            "lo": np.nanpercentile(boots, 2.5, axis=0),
            "hi": np.nanpercentile(boots, 97.5, axis=0)}


# ---------------------------------------------------------------- 事前トレンド
def pretrend_gap(cohorts, cm, want_contrib=False):
    """切替前30日ブロックごとの (処置群 - 対照群) 差分。shape (NBLOCK, NM)

    処置場に開催が無いブロック（尼崎・平和島に実在）は、その場を当該ブロックから
    外して残りのコホートで重みを再正規化する。指標ごとに分母0（例: 堅めが1本も
    無いブロック）も同様に外す。全コホート欠測のブロックのみ nan。"""
    gaps = np.full((NBLOCK, NM), np.nan)
    contrib = np.zeros((NBLOCK, NM), dtype=int)
    for bi in range(NBLOCK):
        vals = np.full((len(cohorts), NM), np.nan)
        wts = np.zeros(len(cohorts))
        for k, c in enumerate(cohorts):
            tvi = TREAT_VI[c]
            wts[k] = AB[tvi, c, bi][AI["n"]]
            if wts[k] == 0:
                continue
            t = np.array(cell(AB[tvi, c, bi], POSB[tvi, c, bi], NEGB[tvi, c, bi]))
            cc = np.array(cell(np.tensordot(cm, AB[CTRL_VI, c, bi], axes=(0, 0)),
                               np.tensordot(cm, POSB[CTRL_VI, c, bi], axes=(0, 0)),
                               np.tensordot(cm, NEGB[CTRL_VI, c, bi], axes=(0, 0))))
            vals[k] = t - cc
        for m in range(NM):
            ok = ~np.isnan(vals[:, m]) & (wts > 0)
            if not ok.any():
                continue
            w = wts[ok] / wts[ok].sum()
            gaps[bi, m] = float((w * vals[ok, m]).sum())
            contrib[bi, m] = int(ok.sum())
    return (gaps, contrib) if want_contrib else gaps


def ols_slope(y):
    """t = -NBLOCK..-1 に対する傾き（1ブロック=30日あたりの変化）"""
    x = np.arange(-NBLOCK, 0, dtype=float)
    out = np.zeros(y.shape[1])
    for m in range(y.shape[1]):
        yy = y[:, m]
        ok = ~np.isnan(yy)
        if ok.sum() < 3:
            out[m] = float("nan"); continue
        xx, yv = x[ok], yy[ok]
        out[m] = np.polyfit(xx, yv, 1)[0]
    return out


def run_pretrend(cohorts, label):
    one = np.ones(len(CONTROL))
    gaps, contrib = pretrend_gap(cohorts, one, want_contrib=True)
    slope = ols_slope(gaps)
    boots = np.zeros((NBOOT, NM))
    nT = len(cohorts)
    for b in range(NBOOT):
        td = [cohorts[i] for i in RNG.integers(0, nT, nT)]
        cm = np.bincount(RNG.integers(0, len(CONTROL), len(CONTROL)),
                         minlength=len(CONTROL)).astype(float)
        boots[b] = ols_slope(pretrend_gap(td, cm))
    return {"label": label, "gaps": gaps, "slope": slope, "contrib": contrib,
            "lo": np.nanpercentile(boots, 2.5, axis=0),
            "hi": np.nanpercentile(boots, 97.5, axis=0)}


# ---------------------------------------------------------------- 実行
if __name__ == "__main__":
    lines = []
    def w(s=""):
        lines.append(s); print(s)

    hds = sorted({r["hd"] for r in ROWS})
    w("=== データとクリーニング ===")
    w("verify_log.csv 生件数        : %d" % N_RAW)
    w("除外 スコア数値化不可        : %d" % BAD["score"])
    w("除外 着順フォーマット異常    : %d" % BAD["chaku"])
    w("除外 主役正誤 不正値         : %d" % BAD["shuyaku"])
    w("除外 波乱正誤 不正値         : %d" % BAD["hairan_mark"])
    tot_excl = sum(BAD.values())
    w("除外合計                     : %d (%.3f%%)" % (tot_excl, 100.0 * tot_excl / N_RAW))
    w("解析対象                     : %d 行" % len(ROWS))
    w("期間                         : %s 〜 %s" % (hds[0], hds[-1]))
    nmix = sum(1 for r in ROWS if r["judged"] == 0)
    w("うち判定「混戦」(指標2・4の対象外): %d 行 (%.1f%%)" % (nmix, 100.0 * nmix / len(ROWS)))
    w("  ※混戦は指標1・3では分母に含める（主役艇とスコアは全レースに存在するため）")
    w()
    if 100.0 * tot_excl / N_RAW > 1.0:
        w("!!! 除外が1%を超えたため中止 !!!"); raise SystemExit(1)

    w("=== 群構成（Phase 1 と同一） ===")
    w("処置群8場: " + " / ".join("%s%s(切替%s)" % (j, n, c) for j, n, c in TREAT))
    w("対照群%d場: " % len(CONTROL) + " ".join("%s%s" % (j, VENUE_NAME[j]) for j in CONTROL))
    w("完全除外  : 11びわこ 24大村")
    w()

    hei = [i for i, t in enumerate(TREAT) if t[0] == "04"][0]
    ALLC = list(range(NCUT))
    NOHEI = [i for i in ALLC if i != hei]

    for res in (run(ALLC, "全8場"), run(NOHEI, "平和島除く7場")):
        w("=" * 78)
        w("【%s】DiD推定量と95%%CI（場クラスタ・ブートストラップ%d回）" % (res["label"], NBOOT))
        w("=" * 78)
        c = res["cells"]
        for m in range(NM):
            w(METRIC_NAMES[m])
            fmt = "%9.4f" if m == 3 else "%9.2f"
            w(("   処置群 前=" + fmt + "  後=" + fmt + "  差=%+9.4f") %
              (c["t_pre"][m], c["t_post"][m], c["t_post"][m] - c["t_pre"][m]))
            w(("   対照群 前=" + fmt + "  後=" + fmt + "  差=%+9.4f") %
              (c["c_pre"][m], c["c_post"][m], c["c_post"][m] - c["c_pre"][m]))
            sig = "有意" if (res["lo"][m] > 0 or res["hi"][m] < 0) else "有意でない"
            w("   DiD = %+9.4f   95%%CI [%+9.4f, %+9.4f]   → %s"
              % (res["did"][m], res["lo"][m], res["hi"][m], sig))
            w()

    # n
    w("=" * 78); w("【各セルの n（verify_log 行数）】"); w("=" * 78)
    for ci, (j, nm, cut) in enumerate(TREAT):
        vi = V_IDX[j]
        tp, ts = A[vi, ci, 0], A[vi, ci, 1]
        cp = A[CTRL_VI, ci, 0].sum(axis=0); cs = A[CTRL_VI, ci, 1].sum(axis=0)
        w("%s%-5s 切替%s : 処置前 %5d / 処置後 %5d ｜ 対照前 %6d / 対照後 %6d"
          % (j, nm, cut, tp[AI["n"]], ts[AI["n"]], cp[AI["n"]], cs[AI["n"]]))
        w("            （うち混戦除く判定対象）処置前 %5d / 処置後 %5d ｜ 対照前 %6d / 対照後 %6d"
          % (tp[AI["judged"]], ts[AI["judged"]], cp[AI["judged"]], cs[AI["judged"]]))
        w("            （堅め）処置後 %4d ／（波乱）処置後 %4d"
          % (ts[AI["katame"]], ts[AI["haran"]]))
    w()

    # 場別
    w("=" * 78); w("【参考】処置場ごとの DiD（n不足のため主結論にしない）"); w("=" * 78)
    one = np.ones(len(CONTROL))
    w("場        " + "".join("%12s" % s for s in ["指標1", "指標1s", "指標2", "AUC", "指標4a", "指標4b"]))
    for ci, (j, nm, cut) in enumerate(TREAT):
        d, _ = estimate([ci], one)
        w("%s%-6s" % (j, nm) + "".join(("%12.4f" if m == 3 else "%12.2f") % d[m] for m in range(NM)))
    w()

    # A. 事前トレンド
    w("=" * 78)
    w("【A】事前トレンドの平行性検定")
    w("    切替前を30日ブロック×%d（=切替前240日）に割り、各ブロックで" % NBLOCK)
    w("    (処置群 − 対照群) の差を取り、その差がブロック番号に対して")
    w("    傾きを持つかを検定する。傾き0＝平行トレンド。")
    w("=" * 78)
    pt = run_pretrend(ALLC, "全8場")
    for m in range(NM):
        w(METRIC_NAMES[m])
        w("   ブロック別の(処置−対照)差 [-8 → -1]: " +
          " ".join(("%8.4f" if m == 3 else "%8.2f") % v for v in pt["gaps"][:, m]))
        w("   寄与コホート数              [-8 → -1]: " +
          " ".join("%8d" % v for v in pt["contrib"][:, m]))
        sig = "平行でない" if (pt["lo"][m] > 0 or pt["hi"][m] < 0) else "平行と矛盾しない"
        w("   傾き(30日あたり) = %+9.4f  95%%CI [%+9.4f, %+9.4f] → %s"
          % (pt["slope"][m], pt["lo"][m], pt["hi"][m], sig))
        w()

    # 感度分析: 加重方法
    w("=" * 78)
    w("【感度分析】コホート加重を「処置場の全行数」→「切替後の行数」に変更")
    w("    切替後が短い場（平和島42日）が全行数加重では過大な重みを持つため。")
    w("=" * 78)
    for res in (run(ALLC, "全8場・切替後n加重", "post"),
                run(NOHEI, "平和島除く7場・切替後n加重", "post")):
        w("[%s]" % res["label"])
        for m in range(NM):
            sig = "有意" if (res["lo"][m] > 0 or res["hi"][m] < 0) else "有意でない"
            w(("  %-38s DiD=%+9.4f  95%%CI [%+9.4f, %+9.4f] %s"
               % (METRIC_NAMES[m][:38], res["did"][m], res["lo"][m], res["hi"][m], sig)))
        w()

    w("=== 切替後の観測日数（verify_log 終端 %s まで） ===" % hds[-1])
    end = d8(hds[-1]); start = d8(hds[0])
    for j, nm, cut in TREAT:
        w("  %s%-5s 切替%s → 後 %3d 日 / 前 %3d 日"
          % (j, nm, cut, (end - d8(cut)).days + 1, (d8(cut) - start).days))

    with open(os.path.join(OUTDIR, "phase2_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
