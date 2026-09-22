# -*- coding: utf-8 -*-
"""検証03 stage3：初めてF1で1コースに入った年ごとの F0→F1（全期間の基準）。組ごとの偶然の幅。
全体の ST差 が stage1 の 0.0158 と一致しなければ止まる。出力は kensho03parts/stage3.json のみ。"""
import json, sys
import numpy as np
sys.path.insert(0, "C:/Users/USER/kensho03parts")
import stage0 as S
import stage1 as T
c = S.collect(); rows = c["rows"]
first = {}
for hd, tb, fn, st, ch in rows:
    if fn == 1: first.setdefault(tb, hd)
pp = T.per_player(rows)[1]
players, obs, nulls = T.perm_block(pp)
if round(float(obs.mean()), 4) != 0.0158: raise SystemExit("全体が stage1 と一致しない")
yr = np.array(["20" + first[t][:2] for t in players])
res = {y: T.summarize(obs[yr == y], nulls[yr == y]) for y in sorted(set(yr))}
json.dump(res, open("stage3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for y, v in res.items(): print(y, v["人数"], v["ST差"], v["最小の差"], v["充足率"], v["帰無で実際以上"])
