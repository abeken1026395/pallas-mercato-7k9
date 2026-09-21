#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data/wakuStats/base.csv の k1 列（枠1の決着）を過去分まで埋める。一度だけローカルで回す。

Kファイル（data/kfiles・ローカル専用）を優先し、無い分は results/*.json から埋める。
base.csv は開催地とレース番号を持たないため、(開催日, 登番, 着) の組で突き合わせる。
同じ日に同じ着で2回枠1に出た選手は、組の中で順に割り当てる（日付が同じなので期間集計は変わらない）。

安全装置（1つでも満たさなければ何も書かずに exit 1）
  1. 既存5列（hd,toban,waku,chaku,st）が全行で1文字も変わらない
  2. 枠1かつ欠場でない行に、空欄の k1 が1行も残らない
  3. Kファイルと results の両方にある組で、決着の一致率が99.5%以上
使い方: python scripts/backfillWakuK1.py [--dry]
"""
import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kparser  # noqa: E402
import updateWakuStats as W  # noqa: E402
from backfillMotorPartsMotorNo import decode_kfile, hd_from_name  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KDIR = os.environ.get("KFILES_DIR", os.path.join(ROOT, "data", "kfiles"))
AGREE_MIN = 0.995


def k_index(days):
    idx = defaultdict(list)
    used = 0
    files = sorted(glob.glob(os.path.join(KDIR, "*.lzh")) +
                   glob.glob(os.path.join(KDIR, "*.txt")) +
                   glob.glob(os.path.join(KDIR, "*.TXT")))
    for path in files:
        hd6, hd8 = hd_from_name(path)
        if not hd6 or hd8 not in days:
            continue
        res = kparser.parse_day(decode_kfile(path), hd6)
        kim = {(r["jcd"], r["rno"]): r.get("kimarite", "") for r in res["races"]}
        for e in res["entries"]:
            if str(e.get("waku", "")).strip() != "1":
                continue
            ch = W.norm_chaku(e.get("chaku", ""))
            if W.is_absent(ch):
                continue
            code = W.k1_code(e.get("shinnyu", ""), ch, kim.get((e["jcd"], e["rno"]), ""))
            idx[(hd8, str(e["toban"]).strip(), ch)].append(code)
        used += 1
    return idx, used


def r_index(days):
    idx = defaultdict(list)
    used = 0
    for p in sorted(glob.glob(os.path.join(W.RESULTS, "*.json"))):
        hd = os.path.basename(p)[:8]
        if hd not in days:
            continue
        for x in W.extract_from_results(p):
            if x["waku"] == "1" and x["k1"]:
                idx[(hd, x["toban"], x["chaku"])].append(x["k1"])
        used += 1
    return idx, used


def main():
    dry = "--dry" in sys.argv
    rows = W.read_base()
    before = [tuple(x[c] for c in W.COLS[:5]) for x in rows]
    days = set(x["hd"] for x in rows)
    kidx, kused = k_index(days)
    ridx, rused = r_index(days)

    both = agree = 0
    for key, kl in kidx.items():
        rl = ridx.get(key)
        if rl and len(rl) == len(kl):
            both += len(kl)
            agree += sum(1 for a, b in zip(sorted(kl), sorted(rl)) if a == b)
    rate = (agree / both) if both else 0.0

    kq = {k: list(v) for k, v in kidx.items()}
    rq = {k: list(v) for k, v in ridx.items()}
    src = {"k": 0, "r": 0}
    blank = []
    for x in rows:
        if x["waku"] != "1" or W.is_absent(x["chaku"]):
            x["k1"] = ""
            continue
        key = (x["hd"], x["toban"], x["chaku"])
        if kq.get(key):
            x["k1"] = kq[key].pop(0)
            src["k"] += 1
        elif rq.get(key):
            x["k1"] = rq[key].pop(0)
            src["r"] += 1
        else:
            x["k1"] = ""
            blank.append(key)

    after = [tuple(x[c] for c in W.COLS[:5]) for x in rows]
    cnt = defaultdict(int)
    for x in rows:
        if x["k1"]:
            cnt[x["k1"]] += 1
    print("ROWS=%d KFILES=%d RESULTS=%d FROM_K=%d FROM_R=%d BLANK=%d" % (
        len(rows), kused, rused, src["k"], src["r"], len(blank)))
    print("AGREE=%d/%d (%.4f)" % (agree, both, rate))
    print("CODES " + " ".join("%s=%d" % (k, cnt[k]) for k in ["e", "s", "m", "z", "x", "o"]))

    ng = []
    if before != after:
        ng.append("1: 既存5列が変わった")
    if blank:
        ng.append("2: 空欄の k1 が %d 行（先頭 %s）" % (len(blank), blank[:5]))
    if rate < AGREE_MIN:
        ng.append("3: 一致率 %.4f < %.3f" % (rate, AGREE_MIN))
    if ng:
        for m in ng:
            print("NG " + m, file=sys.stderr)
        sys.exit(1)
    if dry:
        print("DRY: 書き込みなし")
        return
    W.write_base(rows)
    print("WROTE " + W.BASE)


if __name__ == "__main__":
    main()
