# -*- coding: utf-8 -*-
"""検証01 stage0：Kファイル10年から節を復元し、buildKensho.py と同じ方式で準優メンバーを当てる。
入力 localdata/kfiles01/entries*.csv・races*.csv（読むだけ）。出力は kensho01parts/ だけ。
- s0_setsu.jsonl … 準優のある節ごとの材料（予選最終日の朝の得点率・最終日の出走・進出）
- s0_month.json  … 選手×月の着順点の合計と走数（強さの物差し用）
- s0_summary.json … 再現率・除外件数・kenshoVerify との照合
1か月ずつ流し、場ごとに節1つぶんだけを持つ。"""
import csv
import datetime
import glob
import json
import os
from collections import defaultdict

IN = "C:/Users/USER/boatrace/localdata/kfiles01"
OUT = "C:/Users/USER/kensho01parts/"
VERIFY = "C:/Users/USER/boatrace/data/kenshoVerify.json"
PTS = {1: 10, 2: 8, 3: 6, 4: 4, 5: 2, 6: 1}
EXCL = {"F", "S2"}
SPECIAL = ["特選", "特賞", "選抜", "ドリーム"]
MAXGAP = 3


def d8(hd):
    return "20" + hd


def dt(h8):
    return datetime.date(int(h8[:4]), int(h8[4:6]), int(h8[6:]))


def chaku_num(c):
    return int(c) if c.isdigit() and 1 <= int(c) <= 6 else None


def stf(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


stats = defaultdict(int)
month = defaultdict(lambda: [0, 0])       # (toban, yyyymm) -> [pts, n]
recs = []
fout = open(OUT + "s0_setsu.jsonl", "w", encoding="utf-8")


def process(v, days):
    """days: [(h8, {rno: {"name":..., "ent":[(toban,waku,chaku,st,shinnyu)]}})]"""
    jidx = [i for i, (h, rs) in enumerate(days) if any("準優" in r["name"] for r in rs.values())]
    if not jidx:
        stats["節_準優なし"] += 1
        return
    j = jidx[0]
    jh, jrs = days[j]
    ys = days[:j]
    if len(ys) < 2:
        stats["準優_予選日が2日未満"] += 1
        return
    actual = set(t for r in jrs.values() if "準優" in r["name"] for t, *_ in r["ent"])
    k = len(actual)
    if k == 0:
        stats["準優_出走者なし"] += 1
        return
    pt = defaultdict(int); n = defaultdict(int); one = defaultdict(int)
    ptB = defaultdict(int); nB = defaultdict(int); oneB = defaultdict(int)  # 最終日の前日まで
    bad = set(); badB = set(); last = {}
    final = defaultdict(list)
    fh = ys[-1][0]
    for h, rs in ys:
        for rno in sorted(rs):
            r = rs[rno]
            if "準優" in r["name"] or "優勝戦" in r["name"]:
                continue
            bn = 1 if any(s in r["name"] for s in SPECIAL) else 0
            for t, w, c, st, sh in r["ent"]:
                cn = chaku_num(c)
                n[t] += 1; last[t] = h
                if c in EXCL:
                    bad.add(t)
                if cn:
                    pt[t] += PTS[cn] + bn; one[t] += (cn == 1)
                if h != fh:
                    nB[t] += 1
                    if c in EXCL:
                        badB.add(t)
                    if cn:
                        ptB[t] += PTS[cn] + bn; oneB[t] += (cn == 1)
                else:
                    final[t].append({"w": w, "c": c, "st": st, "sh": sh, "rno": rno, "bn": bn})
    cand = [t for t in n if t not in bad and last.get(t) == fh]
    if not cand:
        stats["準優_候補なし"] += 1
        return
    o = sorted(cand, key=lambda t: (pt[t] / n[t], one[t]), reverse=True)
    hit = len(set(o[:k]) & actual)
    stats["準優の節"] += 1
    stats["延べ定員"] += k
    stats["一致"] += hit
    recs.append({"d": jh, "v": v, "k": k, "hit": hit})
    # 最終日の朝の順位（前日まで）
    candB = [t for t in nB if t not in badB and nB[t] > 0]
    oB = sorted(candB, key=lambda t: (ptB[t] / nB[t], oneB[t]), reverse=True)
    if len(oB) <= k:
        stats["朝の順位_定員以下"] += 1
        return
    border = (ptB[oB[k - 1]] / nB[oB[k - 1]] + ptB[oB[k]] / nB[oB[k]]) / 2
    racers = []
    for t in set(nB) | set(final):
        racers.append({"t": t, "rateB": (ptB[t] / nB[t]) if nB[t] else None, "nB": nB[t],
                       "badB": t in badB, "gap": (ptB[t] / nB[t] - border) if nB[t] else None,
                       "fin": final.get(t, []), "adv": t in actual, "bad": t in bad})
    fout.write(json.dumps({"d": jh, "fd": fh, "v": v, "k": k, "border": border, "days": len(ys),
                           "racers": racers}, ensure_ascii=False) + "\n")


cur = {}   # v -> list of (h8, races)
files = sorted(glob.glob(os.path.join(IN, "entries*.csv")))
for ef in files:
    ym = os.path.basename(ef)[7:13]
    names = {}
    with open(os.path.join(IN, "races%s.csv" % ym), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            names[(r["hd"], r["jcd"], r["rno"])] = r["raceName"]
    byday = defaultdict(lambda: defaultdict(dict))
    with open(ef, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            key = (r["hd"], r["jcd"], r["rno"])
            day = byday[r["hd"]][int(r["jcd"])]
            rno = int(r["rno"])
            if rno not in day:
                day[rno] = {"name": names.get(key, ""), "ent": []}
            day[rno]["ent"].append((r["toban"], int(r["waku"]) if r["waku"].isdigit() else None,
                                    r["chaku"], r["st"], r["shinnyu"]))
            cn = chaku_num(r["chaku"])
            if cn:
                m = month[(r["toban"], "20" + r["hd"][:4])]
                m[0] += PTS[cn]; m[1] += 1
    for hd in sorted(byday):
        h8 = d8(hd)
        for v, rs in byday[hd].items():
            stats["開催（場×日）"] += 1
            b = cur.get(v)
            if b:
                gap = (dt(h8) - dt(b[-1][0])).days
                closed = any("優勝戦" in r["name"] for r in b[-1][1].values())
                if closed or gap > MAXGAP:
                    process(v, b)
                    b = None
            if b is None:
                cur[v] = [(h8, rs)]
            else:
                b.append((h8, rs))
        stats["日数"] += 1
    print(ym, dict(stats), flush=True)
for v, b in cur.items():
    process(v, b)
fout.close()

json.dump({"%s|%s" % k: v for k, v in month.items()}, open(OUT + "s0_month.json", "w", encoding="utf-8"))
acc = stats["一致"] / stats["延べ定員"] * 100
# kenshoVerify との照合
ver = {(x["d"], x["v"]): x for x in json.load(open(VERIFY, encoding="utf-8"))}
mine = {(x["d"], x["v"]): x for x in recs}
both = [k for k in ver if k in mine]
same = sum(1 for k in both if ver[k]["hit"] == mine[k]["hit"] and ver[k]["k"] == mine[k]["k"])
vk = sum(ver[k]["k"] for k in both); vh = sum(ver[k]["hit"] for k in both)
mk = sum(mine[k]["k"] for k in both); mh = sum(mine[k]["hit"] for k in both)
summ = {"stats": dict(stats), "再現率": round(acc, 2), "kenshoVerify_節": len(ver), "重なる節": len(both),
        "定員と一致数がともに同じ節": same, "重なる節_verify再現率": round(vh / vk * 100, 2) if vk else None,
        "重なる節_Kファイル再現率": round(mh / mk * 100, 2) if mk else None,
        "重なる節_定員が同じ": sum(1 for k in both if ver[k]["k"] == mine[k]["k"])}
json.dump(summ, open(OUT + "s0_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summ, ensure_ascii=False))
if acc < 88:
    raise SystemExit("ゲート：再現率が88%未満")
