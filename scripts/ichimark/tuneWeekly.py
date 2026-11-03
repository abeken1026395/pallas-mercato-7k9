#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tuneWeekly.py — 1マークの見立ての作り方を週1で見直す（けん裁定 2026-11-03「2A」）。

やること
  1. 直近28日のレースを学習から外し、それより前だけで学習して、直近28日を当てさせる（今の作り方と候補を同じ条件で）。
  2. 候補＝今の作り方から設定を1つだけ1段ずらしたもの、材料のまとまりを1つだけ出し入れしたもの。
  3. 次の関門をすべて通った候補のうち、誤差がいちばん小さいものに切り替える。1つも通らなければ今のまま。
     関門1：「1コースが逃げたか」の誤差（ブライア）が今より MARGIN 以上小さい
     関門2：15分類全体の対数損失が今より悪くならない
     関門3：格（SG・G1／G2・G3／一般）のどれも、誤差が今より GRADE_TOL を超えて悪くならない（その格が GRADE_MIN レース以上のとき）
  4. 切り替えたら scripts/ichimark/maeConfig.json を書き換える（次の朝の見立てから効く。出した見立ては書き換えない）。
     採用・不採用とも health/ichimarkTune.md に1回分を追記する。

使い方:  python scripts/ichimark/tuneWeekly.py [--dry]   （--dry は書かずに結果だけ出す）
"""
import datetime
import json
import os
import sys

import numpy as np
from sklearn.metrics import log_loss

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildMae as B  # noqa: E402

HOLD_DAYS = 28
MARGIN = 0.001
GRADE_TOL = 0.002
GRADE_MIN = 200
LOG = os.path.join(B.ROOT, "health", "ichimarkTune.md")
STEPS = {"num_leaves": [4, 8, 16], "n_estimators": [150, 250, 400], "min_child_samples": [100, 200, 400],
         "colsample_bytree": [0.5, 0.8]}
GRADES = (("SG・G1", (1, 2)), ("G2・G3", (3, 4)), ("一般", (5,)))


def candidates(cur):
    out = []
    for k, vals in STEPS.items():
        v = cur["params"].get(k)
        i = vals.index(v) if v in vals else None
        near = [vals[j] for j in ((i - 1, i + 1) if i is not None else range(len(vals))) if 0 <= j < len(vals)]
        for nv in near:
            if nv != v:
                out.append({"params": dict(cur["params"], **{k: nv}), "drop": list(cur["drop"]), "what": "%s %s→%s" % (k, v, nv)})
    for g in B.DROP_GROUPS:
        d = [x for x in cur["drop"] if x != g] if g in cur["drop"] else cur["drop"] + [g]
        out.append({"params": dict(cur["params"]), "drop": d, "what": ("%sを使う" if g in cur["drop"] else "%sを使わない") % g})
    return out


def score(cfg, X, y, tr, te):
    m = B.fit(X[tr], y[tr], cfg)
    P = B.proba(m, X[te]); pn = P[:, B.NI]; isn = (y[te] == B.NI).astype(float)
    g = X[te][:, 2]
    byg = {}
    for nm, gs in GRADES:
        s = np.isin(g, gs)
        if s.sum():
            byg[nm] = {"n": int(s.sum()), "brier": round(float(np.mean((pn[s] - isn[s]) ** 2)), 5)}
    return {"brier": round(float(np.mean((pn - isn) ** 2)), 5),
            "logloss": round(float(log_loss(y[te], np.clip(P, 1e-9, 1), labels=range(B.K))), 5), "byGrade": byg}


def passes(c, cur):
    if not c["brier"] <= cur["brier"] - MARGIN:
        return False, "関門1（逃げの誤差が %.4f 以上小さくない）" % MARGIN
    if c["logloss"] > cur["logloss"]:
        return False, "関門2（15分類の対数損失が悪化）"
    for g, v in cur["byGrade"].items():
        cg = c["byGrade"].get(g)
        if v["n"] >= GRADE_MIN and cg and cg["brier"] > v["brier"] + GRADE_TOL:
            return False, "関門3（%sで悪化）" % g
    return True, "通過"


def main():
    dry = "--dry" in sys.argv
    today = datetime.datetime.now(B.JST).strftime("%Y%m%d")
    raw = json.load(open(B.CFG_PATH, encoding="utf-8"))
    cur = B.load_cfg()
    ev, keys, races = B.load_history(today)
    X, y, meta = B.build_training(ev, keys, races)
    d = np.array([m[0] for m in meta])
    last = max(d); cut = B.ymd(last, HOLD_DAYS - 1)
    tr = d < cut; te = d >= cut
    print("学習", int(tr.sum()), "／ 当てさせる", int(te.sum()), "（%s から %s）" % (cut, last), flush=True)
    base = score(cur, X, y, tr, te)
    print("今", cur["id"], base, flush=True)
    rows = []
    for c in candidates(cur):
        s = score(c, X, y, tr, te)
        ok, why = passes(s, base)
        rows.append((c, s, ok, why))
        print(c["what"], s["brier"], s["logloss"], why, flush=True)
    good = sorted([r for r in rows if r[2]], key=lambda r: r[1]["brier"])
    pick = good[0] if good else None
    stamp = datetime.datetime.now(B.JST).strftime("%Y-%m-%d")
    lines = ["", "## %s（当てさせた期間 %s から %s・%dレース／学習 %dレース）" % (stamp, cut, last, int(te.sum()), int(tr.sum())),
             "", "| 作り方 | 逃げの誤差 | 15分類の対数損失 | 判定 |", "|---|---|---|---|",
             "| 今（%s） | %.4f | %.4f | — |" % (cur["id"], base["brier"], base["logloss"])]
    lines += ["| %s | %.4f | %.4f | %s |" % (c["what"], s["brier"], s["logloss"], why) for c, s, ok, why in rows]
    if pick:
        nid = "v%d" % (int(str(cur["id"]).lstrip("v") or 1) + 1)
        since = B.ymd(today, -1)  # 次の朝の見立てから
        lines += ["", "採用：%s → %s（%s）。%s の見立てから。" % (cur["id"], nid, pick[0]["what"], since)]
        raw.update({"id": nid, "since": since, "params": pick[0]["params"], "drop": pick[0]["drop"]})
        raw.setdefault("history", []).append({"id": nid, "since": since, "note": pick[0]["what"],
                                              "holdout": {"from": cut, "to": last, "n": int(te.sum())},
                                              "brier": pick[1]["brier"], "brierPrev": base["brier"]})
    else:
        lines += ["", "不採用：関門を通った候補なし。%s のまま。" % cur["id"]]
    print("\n".join(lines))
    if dry:
        return 0
    if pick:
        with open(B.CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
            f.write("\n")
    new = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8") as f:
        if new:
            f.write("# 1マークの見立て：週1の見直しの記録\n\n`scripts/ichimark/tuneWeekly.py` が毎週1回追記する。関門は同ファイルの冒頭を参照。\n")
        f.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
