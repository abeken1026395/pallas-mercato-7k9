# -*- coding: utf-8 -*-
"""検証03 stage2：隠れF（前の期にFを切り、期の初日に0へ戻った状態）。
F0の1コースのうち、前の期にFを切っていた選手の行を「隠れF」、それ以外を「きれいなF0」とする。
1. 件数と平均ST
2. 同じ選手で、隠れF と きれいなF0 の差（日を単位に入れ替え1,000回）
3. 基準をきれいなF0に限ったときの F0→F1・F0→F2（穴を塞いだら差はどうなるか）
出力は kensho03parts/stage2.json のみ。"""
import json, sys
from collections import defaultdict
import numpy as np
sys.path.insert(0, "C:/Users/USER/kensho03parts")
import stage0 as S
import stage1 as T

def main():
    c = S.collect(); rows = c["rows"]
    # 期ごとにFを切った選手
    fper = defaultdict(set)
    import csv, glob, os
    for path in sorted(glob.glob(os.path.join(S.IN_DIR, "entries*.csv"))):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["chaku"] == "F":
                    fper[S.period_of(S.hd8(r["hd"]))].add(r["toban"])
    periods = sorted(fper)
    def prev(p):
        y, ab = int(p[:4]), p[4]
        return "%dA" % y if ab == "B" else "%dB" % (y - 1)
    first_p = periods[0]
    hid = []; lab_rows = []
    for hd, tb, fn, st, ch in rows:
        p = S.period_of(S.hd8(hd))
        h = fn == 0 and p != first_p and tb in fper.get(prev(p), set())
        lab_rows.append((hd, tb, fn, st, ch, h))
    n0 = sum(1 for r in lab_rows if r[2] == 0 and r[0][:0] == "" and S.period_of(S.hd8(r[0])) != first_p)
    nh = sum(1 for r in lab_rows if r[5])
    sth = [r[3] for r in lab_rows if r[5] and r[3] is not None]
    stc = [r[3] for r in lab_rows if r[2] == 0 and not r[5] and r[3] is not None]
    res = {"最初の期（前の期が無いので判定から外す）": first_p,
           "F0の1コース（最初の期を除く）": n0, "うち隠れF": nh,
           "隠れFの割合": round(nh / n0 * 100, 1),
           "隠れF_平均ST": round(sum(sth) / len(sth), 4), "きれいなF0_平均ST": round(sum(stc) / len(stc), 4)}
    # 2. 同じ選手で 隠れF と きれいなF0（最初の期は使わない）
    by = defaultdict(lambda: {"c": [], "h": []})
    for hd, tb, fn, st, ch, h in lab_rows:
        if fn != 0 or st is None or S.period_of(S.hd8(hd)) == first_p:
            continue
        by[tb]["h" if h else "c"].append((hd, st))
    pp = {tb: (v["c"], v["h"]) for tb, v in by.items() if len(v["c"]) >= S.MIN_F0 and len(v["h"]) >= S.MIN_TGT}
    players, obs, nulls = T.perm_block(pp)
    res["同じ選手_隠れF引くきれいなF0"] = T.summarize(obs, nulls)
    # 3. 基準をきれいなF0に限った F0→F1 / F0→F2（最初の期の行も基準から外す）
    rows_clean = [(hd, tb, (fn if not h else -1), st, ch) for hd, tb, fn, st, ch, h in lab_rows
                  if not (fn == 0 and S.period_of(S.hd8(hd)) == first_p)]
    pp2 = T.per_player(rows_clean)
    out = {}
    for tgt in (1, 2):
        pl, ob, nl = T.perm_block(pp2[tgt])
        out["F0toF%d" % tgt] = T.summarize(ob, nl)
    res["基準をきれいなF0に限った個体内"] = out
    # 同じ最初の期の除外だけをした（隠れFを基準に残した）対照
    rows_ctrl = [(hd, tb, fn, st, ch) for hd, tb, fn, st, ch, h in lab_rows
                 if not (fn == 0 and S.period_of(S.hd8(hd)) == first_p)]
    pp3 = T.per_player(rows_ctrl)
    out = {}
    for tgt in (1, 2):
        pl, ob, nl = T.perm_block(pp3[tgt])
        out["F0toF%d" % tgt] = {"人数": len(ob), "ST差": round(float(ob.mean()), 4),
                                "遅くなった割合": round(float((ob > 0).mean() * 100), 1)}
    res["対照_最初の期だけ外した個体内"] = out
    json.dump(res, open("C:/Users/USER/kensho03parts/stage2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
main()
