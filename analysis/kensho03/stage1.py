# -*- coding: utf-8 -*-
"""検証03 stage1。stage0（buildFmochiTen.py の複製・出力先だけ変更）と同じ入力・同じ定義で、
本文に足す数字を数える。書き込み先は C:/Users/USER/kensho03parts/ だけ。

1. 外した件数（F3以上、STが数値でない1コース、着が1から6でない1コース、個体内で人数条件に届かない選手）
2. 個体内比較を級別（初めてF1／F2で1コースに入った日の級別）に割る
3. 個体内比較の偶然の幅：選手ごとに、1コースに入った「日」を単位に F0/対象 のラベルを入れ替える（1,000回）
   検出できる最小の差 = 帰無の標準偏差 × 2.8、充足率 = 実際の差 ÷ 最小の差
4. 全期間と直前2期の差：両方に入る同じ選手で、2つの値を入れ替える（1,000回）
5. 経験差（切った選手と切っていない選手）：選手を単位にラベルを入れ替える（1,000回）
6. 年ごとの再現：初めてF1で1コースに入った年ごとの個体内のST差
乱数：選手ごとに splitmix64(SEED ^ 登番) で種を作る。分割（選手の並び順・前後半）に依存しないことを自己照合する。
"""
import json
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, "C:/Users/USER/kensho03parts")
import stage0 as S

SEED = 20260922
NPERM = 1000
OUT = "C:/Users/USER/kensho03parts/stage1.json"
MASK = (1 << 64) - 1


def splitmix64(x):
    x = (x + 0x9E3779B97F4A7C15) & MASK
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31)


def rng_for(key):
    return np.random.Generator(np.random.PCG64(splitmix64((SEED ^ key) & MASK)))


def collect_raw():
    """stage0.collect と同じ走査で、F本数を丸める前の値も持つ。"""
    import csv, glob, os
    files = sorted(glob.glob(os.path.join(S.IN_DIR, "entries*.csv")))
    fcnt = defaultdict(int)
    cur = None
    raw = []   # (hd, tb, fraw, st_str, ch)
    for path in files:
        by_day = defaultdict(list)
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                by_day[r["hd"]].append(r)
        for hd in sorted(by_day):
            pk = S.period_of(S.hd8(hd))
            if pk != cur:
                fcnt = defaultdict(int)
                cur = pk
            today_f = []
            for r in by_day[hd]:
                if r["chaku"] == "F":
                    today_f.append(r["toban"])
                if r["shinnyu"] != "1" or r["chaku"] in ("K0", "K1"):
                    continue
                raw.append((hd, r["toban"], fcnt[r["toban"]], r["st"], r["chaku"]))
            for tb in today_f:
                fcnt[tb] += 1
    return raw


def per_player(rows, restrict=None):
    """stage0.indiv と同じ選び方で、選手ごとの (基準の日別 ST 列, 対象の日別 ST 列) を返す。"""
    by = defaultdict(lambda: defaultdict(list))
    for hd, tb, fn, st, ch in rows:
        if st is None:
            continue
        by[tb][fn].append((hd, st))
    first_p = {}
    if restrict == "near":
        for hd, tb, fn, st, ch in rows:
            if fn >= 1 and tb not in first_p:
                first_p[tb] = S.period_of(S.hd8(hd))
    out = {1: {}, 2: {}}
    for tgt in (1, 2):
        for tb, m in by.items():
            base = m.get(0, [])
            if restrict == "near":
                p = first_p.get(tb)
                if not p:
                    continue
                keep = S._near_periods(p)
                base = [x for x in base if S.period_of(S.hd8(x[0])) in keep]
            after = m.get(tgt, [])
            if len(base) >= S.MIN_F0 and len(after) >= S.MIN_TGT:
                out[tgt][tb] = (base, after)
    return out


def day_arrays(base, after):
    """日を単位に、ST の合計と本数、ラベル（1=対象）を並べる。"""
    d = defaultdict(lambda: [0.0, 0, None])
    for hd, st in base:
        d[hd][0] += st; d[hd][1] += 1; d[hd][2] = 0
    for hd, st in after:
        if d[hd][2] == 0:
            raise SystemExit("同じ日に F0 と対象が同居: %s" % hd)
        d[hd][0] += st; d[hd][1] += 1; d[hd][2] = 1
    keys = sorted(d)
    s = np.array([d[k][0] for k in keys]); n = np.array([d[k][1] for k in keys], dtype=float)
    lab = np.array([d[k][2] for k in keys], dtype=bool)
    return s, n, lab


def perm_player(tb, base, after):
    s, n, lab = day_arrays(base, after)
    k = int(lab.sum())
    obs = s[lab].sum() / n[lab].sum() - s[~lab].sum() / n[~lab].sum()
    g = rng_for(int(tb))
    keys = g.random((NPERM, len(s)))
    idx = np.argsort(keys, axis=1)[:, :k]
    sel = np.zeros((NPERM, len(s)), dtype=bool)
    np.put_along_axis(sel, idx, True, axis=1)
    ts = (sel * s).sum(1); tn = (sel * n).sum(1)
    null = ts / tn - (s.sum() - ts) / (n.sum() - tn)
    return obs, null


def perm_block(pp):
    players = sorted(pp)
    obs = []; nulls = []
    for tb in players:
        o, nl = perm_player(tb, *pp[tb])
        obs.append(o); nulls.append(nl)
    obs = np.array(obs); nulls = np.array(nulls)   # (人, NPERM)
    return players, obs, nulls


def summarize(obs, nulls):
    md = nulls.mean(0); slow = (nulls > 0).mean(0) * 100
    sd = md.std(ddof=1)
    real = obs.mean()
    return {
        "人数": int(len(obs)),
        "ST差": round(float(real), 4),
        "遅くなった割合": round(float((obs > 0).mean() * 100), 1),
        "帰無_ST差_平均": round(float(md.mean()), 5),
        "帰無_ST差_SD": round(float(sd), 5),
        "最小の差": round(float(2.8 * sd), 4),
        "充足率": round(float(real / (2.8 * sd)), 2),
        "帰無で実際以上": int((md >= real).sum()),
        "帰無_遅くなった割合_平均": round(float(slow.mean()), 1),
        "帰無_遅くなった割合_最大": round(float(slow.max()), 1),
    }


def main():
    rows_c = S.collect()
    rows = rows_c["rows"]
    idx = S.load_rank()
    res = {}

    # ── 0. stage0 と同じ数字が出るか（分母ゲート）
    iv = S.indiv(rows); ivn = S.indiv(rows, "near")
    gate = (len(rows) == 541018 and iv["F0toF1"]["人数"] == 1746 and iv["F0toF2"]["人数"] == 274
            and ivn["F0toF1"]["人数"] == 1188 and ivn["F0toF2"]["人数"] == 181)
    if not gate:
        raise SystemExit("分母ゲート不一致: %d %s %s" % (len(rows), iv, ivn))
    res["分母ゲート"] = "一致（541,018枠・1,746人・274人・1,188人・181人）"

    # ── 1. 外した件数
    raw = collect_raw()
    if len(raw) != len(rows):
        raise SystemExit("raw と rows の件数が違う")
    fr = defaultdict(int)
    for r in raw:
        fr[min(r[2], 3)] += 1
    nonst = defaultdict(int); nonch = defaultdict(int)
    for hd, tb, fn, st, ch in rows:
        if st is None: nonst[fn] += 1
        if ch is None: nonch[fn] += 1
    st_kinds = defaultdict(int)
    for hd, tb, f, st, ch in raw:
        if S.num_st(st) is None:
            st_kinds[(st or "空")[:1]] += 1
    res["F本数の内訳_1コース"] = {"F0": fr[0], "F1": fr[1], "F2": fr[2], "F3以上": fr[3]}
    res["STが数値でない1コース"] = {"計": sum(nonst.values()), "F本数別": dict(nonst),
                               "先頭文字別": dict(st_kinds)}
    res["着が1から6でない1コース"] = {"計": sum(nonch.values()), "F本数別": dict(nonch)}
    # F1以上で1コースに入ったのに、個体内に届かなかった選手
    had = {1: set(), 2: set()}
    for hd, tb, fn, st, ch in rows:
        if fn in (1, 2): had[fn].add(tb)
    pp_all = per_player(rows); pp_near = per_player(rows, "near")
    res["個体内から外れた選手"] = {
        "F1で1コースに入った選手": len(had[1]), "うち比べた": len(pp_all[1]),
        "F2で1コースに入った選手": len(had[2]), "うち比べた": len(pp_all[2]),
    }

    # ── 2. 級別に割る（初めてその F 本数で1コースに入った日の級別）
    first_day = {1: {}, 2: {}}
    for hd, tb, fn, st, ch in rows:
        if fn in (1, 2) and tb not in first_day[fn]:
            first_day[fn][tb] = hd
    cls = {}
    for key, pp in (("全期間", pp_all), ("直前2期", pp_near)):
        for tgt in (1, 2):
            d = {"A": [], "B": [], "不明": []}
            for tb, (base, after) in pp[tgt].items():
                k = S.kyu_at(idx, tb, S.iso(first_day[tgt][tb])) or ""
                lab = k[:1] if k[:1] in ("A", "B") else "不明"
                b = sum(x[1] for x in base) / len(base); a = sum(x[1] for x in after) / len(after)
                d[lab].append(a - b)
            cls["%s_F0toF%d" % (key, tgt)] = {
                lab: {"人数": len(v), "ST差": round(sum(v) / len(v), 4) if v else None,
                      "遅くなった割合": round(sum(1 for x in v if x > 0) / len(v) * 100, 1) if v else None}
                for lab, v in d.items()}
    res["級別に割った個体内"] = cls

    # ── 3. 個体内の偶然の幅（日を単位に入れ替え）
    perm = {}
    keep_obs = {}
    for key, pp in (("全期間", pp_all), ("直前2期", pp_near)):
        for tgt in (1, 2):
            players, obs, nulls = perm_block(pp[tgt])
            keep_obs[(key, tgt)] = dict(zip(players, obs))
            perm["%s_F0toF%d" % (key, tgt)] = summarize(obs, nulls)
            # 分割不変の自己照合：並び順を逆にして前後半に分けて計算し、合わせて同じになるか
            if key == "全期間" and tgt == 1:
                rev = sorted(pp[tgt], reverse=True)
                h = len(rev) // 2
                parts = []
                for grp in (rev[:h], rev[h:]):
                    for tb in grp:
                        parts.append((tb, perm_player(tb, *pp[tgt][tb])[1]))
                parts.sort()
                n2 = np.array([p[1] for p in parts])
                perm["分割不変の照合_最大誤差"] = float(np.abs(n2 - nulls).max())
                if perm["分割不変の照合_最大誤差"] > 1e-12:
                    raise SystemExit("分割不変が崩れた")
    res["個体内の偶然の幅"] = perm

    # ── 4. 全期間と直前2期の差（同じ選手どうしで2つの値を入れ替え）
    pair = {}
    for tgt in (1, 2):
        a = keep_obs[("全期間", tgt)]; b = keep_obs[("直前2期", tgt)]
        common = sorted(set(a) & set(b))
        x = np.array([a[t] for t in common]); y = np.array([b[t] for t in common])
        real_st = float(y.mean() - x.mean())
        real_sl = float(((y > 0).mean() - (x > 0).mean()) * 100)
        g = rng_for(tgt * 1000003)
        flip = g.random((NPERM, len(common))) < 0.5
        xs = np.where(flip, y, x); ys = np.where(flip, x, y)
        nst = ys.mean(1) - xs.mean(1)
        nsl = ((ys > 0).mean(1) - (xs > 0).mean(1)) * 100
        pair["F0toF%d" % tgt] = {
            "両方に入る選手": len(common),
            "全期間_ST差": round(float(x.mean()), 4), "直前2期_ST差": round(float(y.mean()), 4),
            "ST差の変化": round(real_st, 4), "ST差の最小の差": round(float(2.8 * nst.std(ddof=1)), 4),
            "全期間_遅くなった割合": round(float((x > 0).mean() * 100), 1),
            "直前2期_遅くなった割合": round(float((y > 0).mean() * 100), 1),
            "割合の変化": round(real_sl, 1), "割合の最小の差": round(float(2.8 * nsl.std(ddof=1)), 1),
            "帰無で割合の変化が実際以上に大きい回": int((np.abs(nsl) >= abs(real_sl)).sum()),
            "帰無でST差の変化が実際以上に大きい回": int((np.abs(nst) >= abs(real_st)).sum()),
        }
    res["全期間と直前2期の差"] = pair

    # ── 5. 経験差（選手を単位にラベルを入れ替え）
    f0 = defaultdict(list)
    for hd, tb, fn, st, ch in rows:
        if fn == 0 and st is not None:
            f0[tb].append(st)
    tbs = sorted(t for t, v in f0.items() if len(v) >= S.MIN_F0)
    m = np.array([sum(f0[t]) / len(f0[t]) for t in tbs])
    ever = np.array([t in rows_c["ever_f"] for t in tbs])
    real = float(m[~ever].mean() - m[ever].mean())
    g = rng_for(777)
    nl = []
    for _ in range(NPERM):
        p = g.permutation(ever)
        nl.append(m[~p].mean() - m[p].mean())
    nl = np.array(nl)
    # 切っていない78人の1コース F0 走数
    nn = sorted(len(f0[t]) for t in tbs if t not in rows_c["ever_f"])
    ne = sorted(len(f0[t]) for t in tbs if t in rows_c["ever_f"])
    res["経験差"] = {"切った": int(ever.sum()), "切っていない": int((~ever).sum()),
                   "差_切っていない引く切った": round(real, 4),
                   "最小の差": round(float(2.8 * nl.std(ddof=1)), 4),
                   "帰無で実際以上": int((nl >= real).sum()),
                   "切っていない側_F0走数_中央値": nn[len(nn) // 2],
                   "切った側_F0走数_中央値": ne[len(ne) // 2]}

    # ── 6. 年ごとの再現（初めてF1で1コースに入った年）
    yr = defaultdict(list)
    for tb, o in keep_obs[("全期間", 1)].items():
        yr[first_day[1][tb][:2]].append(o)
    yrn = defaultdict(list)
    for tb, o in keep_obs[("直前2期", 1)].items():
        yrn[first_day[1][tb][:2]].append(o)
    res["年ごと_F0toF1"] = {
        "20" + y: {"全期間": {"人数": len(yr[y]), "ST差": round(float(np.mean(yr[y])), 4)},
                   "直前2期": {"人数": len(yrn.get(y, [])),
                              "ST差": round(float(np.mean(yrn[y])), 4) if yrn.get(y) else None}}
        for y in sorted(yr)}

    # ── 級別の平均ST差（本文の物差し 0.0190）
    gt = S.group_table(rows, idx)
    res["F0のA級とB級の差"] = round(gt["F0B級"]["平均ST"] - gt["F0A級"]["平均ST"], 4)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
