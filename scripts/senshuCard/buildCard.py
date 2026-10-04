"""選手カード card2.json の集計（出走・着・ST・コース別・決まり手・計器・総合）。

使い方: python3 scripts/senshuCard/buildCard.py 最終日YYYYMMDD 出力先 番組フォルダ（fetchPrograms.py の保存先）
- 3期間（直近1年 y1・直近半年 h1・全期間 all）
- 出走は公式の数え方（officialRaces.py）
"""
import bisect
import datetime as dt
import json
import os
import statistics as stt
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import officialRaces as OR  # noqa: E402
import finals as FN  # noqa: E402

ROOT = OR.ROOT
KM = ["逃げ", "差し", "まくり", "まくり差し", "抜き", "恵まれ"]
ITEMS = ["r1", "r2", "in1", "mid3", "out3", "st"]
LO = {"st"}
G = 20


def rhu(x):
    """四捨五入（.5 は切り上げ）"""
    return int(x + 0.5)


def back(d, n):
    return (dt.date(int(d[:4]), int(d[4:6]), int(d[6:])) - dt.timedelta(days=n - 1)).strftime("%Y%m%d")


def new():
    return {"n": 0, "c": [0, 0, 0], "dq": 0, "stS": 0.0, "stN": 0, "f": 0, "late": 0, "sth": [0] * 42, "noSt": 0,
            "co": [[0, 0, 0, 0, 0] for _ in range(6)], "km": [0] * 6, "mae": 0, "wk": 0}


def agg(rows, d0, d1):
    A = {}
    base = [[0, 0, 0, 0] for _ in range(6)]
    allST = [0.0, 0]
    races = set()
    days = set()
    for x in rows:
        if not (d0 <= x['date'] <= d1):
            continue
        races.add(x['rk'])
        days.add(x['date'])
        ch = x['chaku']
        inSt = isinstance(ch, int) and 1 <= ch <= 15   # ST は責任外の失格・出遅れの回も含めて数える（公式の平均STと同じ）
        if not x['off'] and not inSt:
            continue
        a = A.setdefault(str(x['toban']), new())
        st = x['st']
        if inSt:
            if isinstance(st, (int, float)):
                if st < 0:
                    a["f"] += 1
                else:
                    a["stS"] += st
                    a["stN"] += 1
                    if st >= 0.20:
                        a["late"] += 1
                    a["sth"][min(41, int(round(st * 100)))] += 1
                    allST[0] += st
                    allST[1] += 1
            elif x['off']:
                a["noSt"] += 1   # 責任外の出遅れ（L0）は数えない
        if not x['off']:
            continue
        a["n"] += 1
        if ch <= 3:
            a["c"][ch - 1] += 1
        if 6 < ch <= 15:
            a["dq"] += 1
        co = x['course']
        if isinstance(co, int) and 1 <= co <= 6:
            c = a["co"][co - 1]
            c[0] += 1
            if ch <= 3:
                c[ch] += 1
            if ch > 6:
                c[4] += 1
            bb = base[co - 1]
            bb[0] += 1
            if ch <= 3:
                bb[ch] += 1
            w = x['waku']
            if isinstance(w, int):
                a["wk"] += 1
                if co < w:
                    a["mae"] += 1
        if ch == 1 and x['kim'] in KM:
            a["km"][KM.index(x['kim'])] += 1
    return A, base, len(races), len(days), allST


def val(a, k):
    n = a["n"]
    if k == "r1":
        return (a["c"][0] / n * 100, n) if n >= G else None
    if k == "r2":
        return ((a["c"][0] + a["c"][1]) / n * 100, n) if n >= G else None
    if k == "in1":
        x = a["co"][0]
        return (x[1] / x[0] * 100, x[0]) if x[0] >= G else None
    if k == "mid3":
        n2 = a["co"][1][0] + a["co"][2][0]
        t = sum(a["co"][i][1] + a["co"][i][2] + a["co"][i][3] for i in (1, 2))
        return (t / n2 * 100, n2) if n2 >= G else None
    if k == "out3":
        n2 = sum(a["co"][i][0] for i in (3, 4, 5))
        t = sum(a["co"][i][1] + a["co"][i][2] + a["co"][i][3] for i in (3, 4, 5))
        return (t / n2 * 100, n2) if n2 >= G else None
    if k == "st":
        return (a["stS"] / a["stN"], a["stN"]) if a["stN"] >= G else None


def hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def nameParts(rows, names):
    """np：results の氏名（最後に出た表記）を空白で分け、つなげて racerStats の name と同じなら2つ。kp：racerStats の kana をひらがなにして分け、数が np と合えばそのまま"""
    last = {}
    for x in rows:
        if x.get('name'):
            last[str(x['toban'])] = x['name']
    out = {}
    for no, p in names.items():
        nm = last.get(no, "")
        sp = [t for t in nm.replace("\u3000", " ").split(" ") if t]
        npv = sp if len(sp) == 2 and "".join(sp) == p["name"] else [p["name"]]
        kana = hira(p.get("kana") or "")
        ks = [t for t in kana.replace("\u3000", " ").split(" ") if t]
        kpv = ks if len(ks) == len(npv) else ["".join(ks)]
        out[no] = (npv, kpv)
    return out


def build(last, rawDir):
    rows = OR.load(last)
    rows.sort(key=lambda x: x["date"])   # 日付順（足した Kファイルの行もその日の位置に。ST の合計の順番をそろえる）
    first = min(x['date'] for x in rows)
    WIN = {"y1": (back(last, 365), last, "直近1年"), "h1": (back(last, 182), last, "直近半年"), "all": (first, last, "全期間")}
    names = {p["no"]: p for p in json.load(open(os.path.join(ROOT, "docs/data/racerStats.json"), encoding='utf-8'))["players"]}
    prof = json.load(open(os.path.join(ROOT, "docs/players/profile.json"), encoding='utf-8'))
    out = {"players": {}, "win": {}, "items": ITEMS}
    NP = nameParts(rows, names)
    F, empty = FN.collectAll(rawDir, rows, last, os.path.join(ROOT, "data", "senshuCard", "finalsHistory.json"))
    ycu, yco = FN.tally(F, "20170101", last)
    out["yc"] = {"from": "20170101", "to": last, "finals": len(F), "canceled": sum(1 for f in F if not f["win"]), "empty": empty,
                 "grades": ["計", "SG", "G1", "G2", "G3", "一般", "シリーズ"]}
    for wk, (d0, d1, lab) in WIN.items():
        A, base, races, days, allST = agg(rows, d0, d1)
        wyu, wyo = FN.tally(F, d0, d1)
        vals = {k: {} for k in ITEMS}
        for no, a in A.items():
            for k in ITEMS:
                v = val(a, k)
                if v:
                    vals[k][no] = v
        stat = {}
        for k in ITEMS:
            xs = sorted(round(v[0], 10) for v in vals[k].values())   # 同値は10桁で丸めて判定
            N = len(xs)
            m = stt.mean(xs)
            s = stt.pstdev(xs)
            stat[k] = (m, s, N)
            for no, (x, n) in vals[k].items():
                xr = round(x, 10)
                lo = bisect.bisect_left(xs, xr)
                hi = bisect.bisect_right(xs, xr)
                better = lo if k in LO else N - hi
                same = hi - lo
                top = max(1, rhu((better + same / 2) / N * 100))
                dev = 50 + 10 * (x - m) / s * (-1 if k in LO else 1)
                vals[k][no] = (x, n, top, N, round(dev, 1), dev)
        ov = {}
        for no in A:
            ds = [vals[k][no][5] for k in ITEMS if no in vals[k]]
            if len(ds) >= 4:
                ov[no] = sum(ds) / len(ds)
        xs = sorted(round(v, 10) for v in ov.values())
        N = len(xs)
        for no, x in ov.items():
            hi = bisect.bisect_right(xs, round(x, 10))
            lo = bisect.bisect_left(xs, round(x, 10))
            ov[no] = [round(x, 1), max(1, rhu((N - hi + (hi - lo) / 2) / N * 100)), N]
        out["win"][wk] = {"from": d0, "to": d1, "label": lab, "races": races, "days": days, "base": base,
                          "mean": {k: [round(stat[k][0], 4), round(stat[k][1], 4), stat[k][2]] for k in ITEMS},
                          "stAll": [round(allST[0] / allST[1], 4), allST[1]],
                          "finals": sum(1 for f in F if d0 <= f["d"] <= d1 and f["win"])}
        for no, a in A.items():
            if no not in names:
                continue
            P = out["players"].setdefault(no, {"name": names[no]["name"], "branch": names[no]["branch"], "rank": names[no]["rank"],
                                               "age": names[no].get("age"), "tag": prof.get(no, {}).get("tagline") or prof.get(no, {}).get("catch", ""), "w": {},
                                               "np": NP[no][0], "kp": NP[no][1], "yc": [ycu.get(no, [0] * 7), yco.get(no, [0] * 7)]})
            P["w"][wk] = {"n": a["n"], "c": a["c"], "dq": a["dq"], "st": [round(a["stS"], 2), a["stN"], a["f"], a["late"]],
                          "sth": a["sth"], "noSt": a["noSt"], "co": a["co"], "km": a["km"], "mae": [a["mae"], a["wk"]],
                          "it": {k: [round(vals[k][no][0], 4)] + list(vals[k][no][1:5]) for k in ITEMS if no in vals[k]},
                          "ov": ov.get(no), "yu": wyu.get(no, [0] * 7), "yo": wyo.get(no, [0] * 7)[0]}
    return out, rows


if __name__ == '__main__':
    last = sys.argv[1] if len(sys.argv) > 1 else None
    dst = sys.argv[2] if len(sys.argv) > 2 else '/tmp/card2.json'
    out, _ = build(last, sys.argv[3])
    json.dump(out, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
    print('players', len(out['players']))
