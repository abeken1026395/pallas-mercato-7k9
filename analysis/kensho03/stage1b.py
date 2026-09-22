# -*- coding: utf-8 -*-
"""stage1 の追補。級別セルごとの偶然の幅、A級とB級の差の偶然の幅、外れた選手数（キー重複の修正）、
切っていない78人の級別。出力は kensho03parts/stage1b.json のみ。"""
import json, sys
from collections import defaultdict
import numpy as np
sys.path.insert(0, "C:/Users/USER/kensho03parts")
import stage0 as S
import stage1 as T

def main():
    c = S.collect(); rows = c["rows"]; idx = S.load_rank()
    res = {}
    had = {1: set(), 2: set()}
    first_day = {1: {}, 2: {}}
    for hd, tb, fn, st, ch in rows:
        if fn in (1, 2):
            had[fn].add(tb)
            first_day[fn].setdefault(tb, hd)
    pp = {"全期間": T.per_player(rows), "直前2期": T.per_player(rows, "near")}
    res["個体内から外れた選手"] = {"F1で1コースに入った選手": len(had[1]), "F1で比べた": len(pp["全期間"][1]),
                           "F2で1コースに入った選手": len(had[2]), "F2で比べた": len(pp["全期間"][2])}
    cell = {}
    for key in ("全期間", "直前2期"):
        for tgt in (1, 2):
            players, obs, nulls = T.perm_block(pp[key][tgt])
            lab = np.array([(S.kyu_at(idx, tb, S.iso(first_day[tgt][tb])) or "?")[:1] for tb in players])
            out = {}
            for L in ("A", "B"):
                m = lab == L
                out[L] = T.summarize(obs[m], nulls[m])
            # A と B の差：級のラベルだけを選手の間で入れ替える
            real = obs[lab == "B"].mean() - obs[lab == "A"].mean()
            g = T.rng_for(tgt * 7919 + (1 if key == "全期間" else 2))
            nl = np.array([ (lambda p: obs[p == "B"].mean() - obs[p == "A"].mean())(g.permutation(lab)) for _ in range(T.NPERM)])
            out["B引くA"] = {"差": round(float(real), 4), "最小の差": round(float(2.8 * nl.std(ddof=1)), 4),
                           "充足率": round(float(real / (2.8 * nl.std(ddof=1))), 2),
                           "帰無で絶対値が実際以上": int((np.abs(nl) >= abs(real)).sum())}
            cell["%s_F0toF%d" % (key, tgt)] = out
    res["級別セル"] = cell
    # 切っていない選手の級別（F0で1コースに入った最初の日）
    f0first = {}
    f0n = defaultdict(int)
    for hd, tb, fn, st, ch in rows:
        if fn == 0 and st is not None:
            f0n[tb] += 1; f0first.setdefault(tb, hd)
    never = [t for t in f0n if f0n[t] >= S.MIN_F0 and t not in c["ever_f"]]
    k = defaultdict(int)
    for t in never:
        k[(S.kyu_at(idx, t, S.iso(f0first[t])) or "?")[:1]] += 1
    res["切っていない選手_最初の級別"] = dict(k)
    json.dump(res, open("C:/Users/USER/kensho03parts/stage1b.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
main()
