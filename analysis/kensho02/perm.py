# 検証02：節の中の係数（着順点・ST）が偶然の範囲かを、節の中で日のラベルを入れ替えて確かめる。読むだけ。
import sys, statistics, json
import numpy as np
sys.path.insert(0, "C:/Users/USER/kensho02parts")
import bt as B
female = B.load_female(); wt = B.load_weights(); c = B.collect(wt, female); a = B.analyze(c, female)
dw, dp, dst = c["day_w"], c["day_p"], c["day_st"]
sched = {}
for (tb, j, hd) in dw: sched.setdefault((tb, j), []).append(hd)
W = []; Pp = []
for (tb, j), hds in sched.items():
    for g in B.split_setsu(hds):
        ws = np.array([statistics.mean(dw[(tb, j, h)]) for h in g]); ps = np.array([statistics.mean(dp[(tb, j, h)]) for h in g])
        W.append(ws - ws.mean()); Pp.append(ps - ps.mean())
sxx = sum((w*w).sum() for w in W); real = sum((w*p).sum() for w, p in zip(W, Pp)) / sxx
print("n_setsu", len(W), "coef", round(real, 4), "build", round(a["coef_pt"], 4))
rng = np.random.Generator(np.random.PCG64(20260922))
# 長さごとにまとめて入れ替える
from collections import defaultdict
byL = defaultdict(list)
for w, p in zip(W, Pp): byL[len(w)].append((w, p))
null = np.zeros(1000)
for L, lst in byL.items():
    Wm = np.array([x[0] for x in lst]); Pm = np.array([x[1] for x in lst])
    for r in range(1000):
        idx = np.argsort(rng.random(Wm.shape), axis=1)
        null[r] += (np.take_along_axis(Wm, idx, 1) * Pm).sum()
null /= sxx
sd = null.std(ddof=1)
out = {"coef": round(real, 4), "null_mean": round(float(null.mean()), 4), "null_sd": round(float(sd), 4),
       "mde": round(float(2.8*sd), 4), "ratio": round(float(real/(2.8*sd)), 2), "exceed_abs": int((np.abs(null) >= abs(real)).sum()),
       "sd_w": round(a["sd_w"], 4), "eff_pt": round(a["eff_pt"], 4), "n_setsu": a["n_setsu"], "n_rides": c["n_rides"], "n_setsu_rides": a["n_setsu_rides"], "n_races": c["n_races"], "days": len(c["days"])}
print(json.dumps(out, ensure_ascii=False))
json.dump(out, open("perm.json", "w", encoding="utf-8"), ensure_ascii=False)
