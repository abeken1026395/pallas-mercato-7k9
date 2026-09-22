# -*- coding: utf-8 -*-
"""検証01 stage2：ボーダーでの段差（勝負駆けの上乗せ）を測る。
stage1 の「崖っぷち−それ以外」は、ボーダーからの距離に沿った調子の傾きを拾うため、ここで直す。
- ボーダーからの距離を0.25点刻みに分け、±0.5の窓の外（±3.0の内）で2次式を当て、窓の中の予測と実際の差を段差とする
- 偶然の幅：節を単位に1,000回再標本（種20260922）→ 段差の標準偏差×2.8 を最小の差
- 偽の窓：窓の中心をボーダー以外（±1.0から±2.0）に置いて同じ計算をし、段差の散らばりを見る
出力は kensho01parts/s2.json のみ。stage1.py の集計をそのまま読み込む。"""
import json
import sys
from collections import defaultdict

import numpy as np

sys.argv = ["stage1"]
import importlib.util
spec = importlib.util.spec_from_file_location("s1", "C:/Users/USER/kensho01parts/stage1_core.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
rows = S.rows
D = "C:/Users/USER/kensho01parts/"
W = 0.25


def fit_bump(g, y, center=0.0, half=0.5, span=3.0):
    inwin = np.abs(g - center) <= half
    out = (~inwin) & (np.abs(g - center) <= span)
    bins = np.floor((g - center) / W)
    # 2次式を窓の外の点に直接当てる（点ごと）
    X = np.vstack([np.ones(out.sum()), g[out] - center, (g[out] - center) ** 2]).T
    beta, *_ = np.linalg.lstsq(X, y[out], rcond=None)
    xi = g[inwin] - center
    pred = beta[0] + beta[1] * xi + beta[2] * xi ** 2
    return float(y[inwin].mean() - pred.mean()), int(inwin.sum())


def analyze(sel, key, label):
    xs = [x for x in sel if x[key] is not None]
    g = np.array([x["gap"] for x in xs]); y = np.array([x[key] for x in xs])
    sid = np.array([hash_setsu(x) for x in xs])
    real, n = fit_bump(g, y)
    # 節を単位に再標本
    uniq, inv = np.unique(sid, return_inverse=True)
    groups = defaultdict(list)
    for i, k in enumerate(inv):
        groups[k].append(i)
    gl = [np.array(groups[k]) for k in range(len(uniq))]
    rng = np.random.Generator(np.random.PCG64(20260922))
    bs = []
    for _ in range(1000):
        pick = rng.integers(0, len(gl), len(gl))
        idx = np.concatenate([gl[k] for k in pick])
        bs.append(fit_bump(g[idx], y[idx])[0])
    sd = float(np.std(bs, ddof=1))
    plac = {}
    for c in (-2.0, -1.75, -1.5, -1.25, -1.0, 1.0, 1.25, 1.5, 1.75, 2.0):
        plac[str(c)] = round(fit_bump(g, y, center=c)[0], 4)
    pv = np.array(list(plac.values()))
    return {"対象": label, "窓の中の人日": n, "段差": round(real, 4), "再標本SD": round(sd, 4),
            "最小の差": round(2.8 * sd, 4), "充足率": round(real / (2.8 * sd), 2),
            "偽の窓の段差": plac, "偽の窓で絶対値が実際以上": int((np.abs(pv) >= abs(real)).sum())}


def hash_setsu(x):
    return int(x["fd"]) * 100 + int(x.get("v", 0))


out = {}
out["着順点_全体"] = analyze(rows, "res", "着順点の残差（枠×強さ×年）")
out["ST_全体"] = analyze(rows, "resst", "STの残差（進入×強さ×年）")
out["着順点_A級"] = analyze([x for x in rows if x["kyu"] == "A"], "res", "A級")
out["着順点_B級"] = analyze([x for x in rows if x["kyu"] == "B"], "res", "B級")
yr = {}
for y in sorted(set(x["yr"] for x in rows)):
    r = analyze([x for x in rows if x["yr"] == y], "res", y)
    yr[y] = {"段差": r["段差"], "最小の差": r["最小の差"], "充足率": r["充足率"]}
out["着順点_年ごと"] = yr
# 帯ごとの図用：0.25点刻みの平均
curve = defaultdict(lambda: [0.0, 0, 0.0, 0])
for x in rows:
    if -3 <= x["gap"] <= 3:
        b = round(np.floor(x["gap"] / W) * W + W / 2, 3)
        c = curve[b]
        if x["res"] is not None:
            c[0] += x["res"]; c[1] += 1
        if x["resst"] is not None:
            c[2] += x["resst"]; c[3] += 1
out["0.25刻み"] = {str(k): {"着順点残差": round(v[0] / v[1], 4), "n": v[1], "ST残差": round(v[2] / v[3], 5)}
                  for k, v in sorted(curve.items())}
json.dump(out, open(D + "s2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "0.25刻み"}, ensure_ascii=False, indent=1))
