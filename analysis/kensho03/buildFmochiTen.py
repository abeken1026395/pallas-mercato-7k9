# -*- coding: utf-8 -*-
"""検証03（F持ちのイン）の10年集計。localdata/ だけを読み、localdata/ に書く。

入力:
  localdata/kfilesTen/entries*.csv   … Kファイル由来（kdataFromLzh.py の出力）
  C:/Users/USER/bfiles/rankHistory.json … 級別の変化点（parseBfiles.py の出力）
出力:
  localdata/fmochiTen.json           … 集計結果
標準出力にも要点を出す。docs/ にもリポジトリにも書かない。

F本数の定義: 各期の初日（5/1・11/1）に0へ戻し、着欄=F を累積する。出走表のF表記と同じ。
"""
import bisect
import csv
import glob
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_DIR = os.path.join(ROOT, "localdata", "kfilesTen")
RANK = r"C:\Users\USER\bfiles\rankHistory.json"
OUT = os.path.join(ROOT, "localdata", "fmochiTen.json")

MIN_F0 = 10          # 個体内比較でF0側に必要な走数
MIN_TGT = 3          # 個体内比較で対象側に必要な走数
# 罰則が変わった境目（一次確認済みの3点。境界日は本文の数え方欄に明記する）
BOUNDS = ["2022-05-01", "2023-04-01", "2025-05-01"]


def hd8(hd):
    return "20" + hd


def iso(hd):
    h = hd8(hd)
    return "%s-%s-%s" % (h[:4], h[4:6], h[6:])


def period_of(h8):
    """期の識別子。5/1 と 11/1 で切り替わる。"""
    y, md = h8[:4], h8[4:]
    if md >= "1101":
        return y + "B"
    if md >= "0501":
        return y + "A"
    return str(int(y) - 1) + "B"


def load_rank():
    if not os.path.exists(RANK):
        raise SystemExit("fmochiTen: 級別ファイルが無い: %s" % RANK)
    with open(RANK, encoding="utf-8") as f:
        d = json.load(f)
    idx = {}
    for toban, v in d.items():
        days = [c[0] for c in v["changes"]]
        kyus = [c[1] for c in v["changes"]]
        idx[toban] = (days, kyus)
    return idx


def kyu_at(idx, toban, day):
    """その日の級別。変化点より前なら None。"""
    e = idx.get(toban)
    if not e:
        return None
    days, kyus = e
    i = bisect.bisect_right(days, day) - 1
    if i < 0:
        return None
    return kyus[i]


def num_st(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v


def num_chaku(s):
    return int(s) if s.isdigit() and 1 <= int(s) <= 6 else None


def collect():
    files = sorted(glob.glob(os.path.join(IN_DIR, "entries*.csv")))
    if not files:
        raise SystemExit("fmochiTen: entries が無い: %s" % IN_DIR)
    fcnt = defaultdict(int)
    cur = None
    rows = []          # 1コースの行 (hd, toban, fnum, st, chaku)
    ever_f = set()
    f_total = 0
    days = set()
    absent = 0
    for path in files:
        by_day = defaultdict(list)
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                by_day[r["hd"]].append(r)
        for hd in sorted(by_day):
            h8 = hd8(hd)
            pk = period_of(h8)
            if pk != cur:
                fcnt = defaultdict(int)
                cur = pk
            days.add(hd)
            today_f = []
            for r in by_day[hd]:
                ch = r["chaku"]
                tb = r["toban"]
                if ch == "F":
                    today_f.append(tb)
                    ever_f.add(tb)
                    f_total += 1
                if r["shinnyu"] != "1":
                    continue
                if ch in ("K0", "K1"):
                    absent += 1
                    continue
                rows.append((hd, tb, min(fcnt[tb], 2), num_st(r["st"]), num_chaku(ch)))
            for tb in today_f:
                fcnt[tb] += 1
    return {"rows": rows, "ever_f": ever_f, "f_total": f_total,
            "days": sorted(days), "absent": absent}


def group_table(rows, idx):
    acc = {}
    for f in (0, 1, 2):
        for lab in ("A", "B"):
            acc[(f, lab)] = {"n": 0, "sts": [], "chn": 0, "win": 0}
    cache = {}
    for hd, tb, fn, st, ch in rows:
        key = (tb, hd)
        k = cache.get(key)
        if k is None:
            k = kyu_at(idx, tb, iso(hd)) or ""
            cache[key] = k
        if not k:
            continue
        a = acc.get((fn, k[0]))
        if a is None:
            continue
        a["n"] += 1
        if st is not None:
            a["sts"].append(st)
        if ch is not None:
            a["chn"] += 1
            if ch == 1:
                a["win"] += 1
    out = {}
    for (f, lab), a in acc.items():
        out["F%d%s級" % (f, lab)] = {
            "枠数": a["n"], "ST本数": len(a["sts"]),
            "平均ST": round(sum(a["sts"]) / len(a["sts"]), 4) if a["sts"] else None,
            "着本数": a["chn"],
            "1着率": round(a["win"] / a["chn"] * 100, 1) if a["chn"] else None,
        }
    return out


def indiv(rows, restrict=None):
    """個体内比較。restrict='near' なら F0側をFを切る直前2期に限る。"""
    by = defaultdict(lambda: defaultdict(list))
    for hd, tb, fn, st, ch in rows:
        if st is None:
            continue
        by[tb][fn].append((hd, st))
    first_f_period = {}
    if restrict == "near":
        seen = {}
        for hd, tb, fn, st, ch in rows:
            if fn >= 1 and tb not in seen:
                seen[tb] = period_of(hd8(hd))
        first_f_period = seen
    res = {}
    for tgt in (1, 2):
        diffs = []
        for tb, m in by.items():
            base = m.get(0, [])
            if restrict == "near":
                p = first_f_period.get(tb)
                if not p:
                    continue
                keep = _near_periods(p)
                base = [x for x in base if period_of(hd8(x[0])) in keep]
            after = m.get(tgt, [])
            if len(base) >= MIN_F0 and len(after) >= MIN_TGT:
                b = sum(x[1] for x in base) / len(base)
                a = sum(x[1] for x in after) / len(after)
                diffs.append(a - b)
        res["F0toF%d" % tgt] = {
            "人数": len(diffs),
            "ST差": round(sum(diffs) / len(diffs), 4) if diffs else None,
            "遅くなった割合": round(sum(1 for x in diffs if x > 0) / len(diffs) * 100, 1)
                              if diffs else None,
        }
    return res


def _near_periods(p):
    y, ab = int(p[:4]), p[4]
    if ab == "B":
        return {p, "%dA" % y}
    return {p, "%dB" % (y - 1)}


def experience(rows, ever_f):
    f0 = defaultdict(list)
    for hd, tb, fn, st, ch in rows:
        if fn == 0 and st is not None:
            f0[tb].append(st)
    a = [sum(v) / len(v) for tb, v in f0.items() if len(v) >= MIN_F0 and tb in ever_f]
    b = [sum(v) / len(v) for tb, v in f0.items() if len(v) >= MIN_F0 and tb not in ever_f]
    return {
        "切った選手": {"人数": len(a), "F0時ST": round(sum(a) / len(a), 4) if a else None},
        "切っていない選手": {"人数": len(b), "ST": round(sum(b) / len(b), 4) if b else None},
    }


def by_rule(rows):
    out = {}
    edges = [""] + BOUNDS + ["9999-99-99"]
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        sel = [r for r in rows if lo <= iso(r[0]) < hi]
        g = {}
        for f in (0, 1):
            sts = [r[3] for r in sel if r[2] == f and r[3] is not None]
            g["F%d" % f] = {"本数": len(sts),
                            "平均ST": round(sum(sts) / len(sts), 4) if sts else None}
        d = None
        if g["F0"]["平均ST"] is not None and g["F1"]["平均ST"] is not None:
            d = round(g["F1"]["平均ST"] - g["F0"]["平均ST"], 4)
        out["%s〜%s" % (lo or "開始", hi if hi != "9999-99-99" else "現在")] = {
            "F0": g["F0"], "F1": g["F1"], "差": d}
    return out


def attackers(rows):
    """F2の状態で1コースに入り、速いSTを含む選手を数える。"""
    by = defaultdict(list)
    for hd, tb, fn, st, ch in rows:
        if fn == 2 and st is not None:
            by[tb].append(st)
    out = []
    for tb, v in by.items():
        if len(v) >= 3 and min(v) <= 0.06:
            out.append({"登番": tb, "走数": len(v), "最速ST": round(min(v), 2),
                        "平均ST": round(sum(v) / len(v), 4)})
    out.sort(key=lambda x: x["最速ST"])
    return {"人数": len(out), "上位5人": out[:5]}


def main():
    idx = load_rank()
    c = collect()
    rows = c["rows"]
    res = {
        "集計期間": {"開始": iso(c["days"][0]), "終了": iso(c["days"][-1]),
                     "日数": len(c["days"])},
        "1コース有効枠": len(rows),
        "うちST数値": sum(1 for r in rows if r[3] is not None),
        "うち着数値": sum(1 for r in rows if r[4] is not None),
        "除いた欠場": c["absent"],
        "F発生": c["f_total"],
        "群間": group_table(rows, idx),
        "個体内_全期間": indiv(rows),
        "個体内_直前2期": indiv(rows, restrict="near"),
        "経験差": experience(rows, c["ever_f"]),
        "罰則区間別": by_rule(rows),
        "F2でも攻める選手": attackers(rows),
        "定義": {
            "F本数": "各期の初日(5/1・11/1)に0へ戻し、着欄=Fを累積",
            "個体内F0側の最低走数": MIN_F0,
            "個体内対象側の最低走数": MIN_TGT,
            "罰則の境目": BOUNDS,
            "級別の出典": "Bファイル(番組表)由来の rankHistory.json",
        },
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print("書き出し: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
