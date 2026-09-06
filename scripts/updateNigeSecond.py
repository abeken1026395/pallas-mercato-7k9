#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1コース逃げ時の2着コース分布（選手別・直近730日ローリング）を更新する。

正本  : data/nigeSecond/base.csv   列 hd,jcd,rno,toban,shinnyu,chaku（1レース6行・逃げ決着のみ）
入力  : results/YYYYMMDD.json     正本の最大hdより新しい日だけ読む
出力  : docs/data/nigeSecond.json  回数のみ（率と縮小推定は表示側で計算）

抽出条件（Kファイル由来の正本と同一。417日の突合で不一致0件を確認済み）
  決まり手が「逃げ」 かつ コース1の艇が着1 かつ 6艇のコースが{1..6} かつ 2着が一意
  決まり手が null のレース（1着同着）は逃げでないとして除外
"""
import csv
import glob
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "data", "nigeSecond", "base.csv")
OUT = os.path.join(ROOT, "docs", "data", "nigeSecond.json")
RESULTS = os.path.join(ROOT, "results")
WINDOW_DAYS = 730
COLS = ["hd", "jcd", "rno", "toban", "shinnyu", "chaku"]
MIN_N_FOR_TAU = 8


def jst_now():
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")


def norm_chaku(v):
    """着コードの表記ゆれを吸収する。Kファイル由来は "01".."06"、results 由来は "1".."6"。
    失格・欠場等（S0/F/L0 等）はそのまま返す（2着判定に一致しないだけ）。"""
    v = str(v).strip()
    return v.lstrip("0") or v


def read_base():
    if not os.path.exists(BASE):
        return []
    with io.open(BASE, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        rows = []
        for x in r:
            x = dict(x)
            x["chaku"] = norm_chaku(x.get("chaku"))
            x["jcd"] = str(x.get("jcd")).zfill(2)
            x["rno"] = str(x.get("rno")).strip().rstrip("R").lstrip("0") or "0"
            rows.append(x)
        return rows


def write_base(rows):
    rows.sort(key=lambda x: (x["hd"], x["jcd"], int(x["rno"]), int(x["shinnyu"])))
    os.makedirs(os.path.dirname(BASE), exist_ok=True)
    with io.open(BASE, "w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS)
        for x in rows:
            w.writerow([x[c] for c in COLS])


def extract_from_results(path):
    hd = os.path.basename(path)[:8]
    with io.open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    out = []
    for r in d.get("結果", []) or []:
        if r.get("決まり手") != "逃げ":
            continue
        boats = r.get("艇") or []
        if len(boats) != 6:
            continue
        courses = sorted(int(b.get("コース") or 0) for b in boats)
        if courses != [1, 2, 3, 4, 5, 6]:
            continue
        first = [b for b in boats if b.get("着") == 1]
        second = [b for b in boats if b.get("着") == 2]
        if len(first) != 1 or int(first[0].get("コース")) != 1 or len(second) != 1:
            continue
        jcd = str(r.get("場コード")).zfill(2)
        rno = str(r.get("レース")).rstrip("R")
        for b in boats:
            out.append({
                "hd": hd, "jcd": jcd, "rno": rno,
                "toban": str(b.get("登番")),
                "shinnyu": str(int(b.get("コース"))),
                "chaku": str(b.get("着") if b.get("着") is not None else ""),
            })
    return out


def build_json(rows, meta_from, meta_to, days_added):
    # レース単位に組み直す
    races = {}
    for x in rows:
        races.setdefault((x["hd"], x["jcd"], x["rno"]), []).append(x)
    base = [0, 0, 0, 0, 0]
    cells = {}
    for key, boats in races.items():
        if len(boats) != 6:
            continue
        sec = [b for b in boats if b["chaku"] == "2"]
        if len(sec) != 1:
            continue
        sc = int(sec[0]["shinnyu"])
        if sc < 2 or sc > 6:
            continue
        base[sc - 2] += 1
        for b in boats:
            c = int(b["shinnyu"])
            cell = cells.setdefault(b["toban"], {}).setdefault(str(c), [0, 0, 0, 0, 0, 0])
            cell[0] += 1
            cell[sc - 1] += 1
    n_races = sum(base)

    # 縮小推定パラメータ p, tau2 を (進入コースc, 2着コースX) ごとに
    shrink = {}
    for c in range(1, 7):
        shrink[str(c)] = {}
        for x in range(2, 7):
            ks = []
            for toban, cs in cells.items():
                cell = cs.get(str(c))
                if cell and cell[0] >= MIN_N_FOR_TAU:
                    ks.append((cell[x - 1], cell[0]))
            if not ks:
                shrink[str(c)][str(x)] = [0.0, 0.000001]
                continue
            K = sum(a for a, _ in ks)
            N = sum(b for _, b in ks)
            p = K / N if N else 0.0
            m = len(ks)
            if m >= 2 and 0.0 < p < 1.0:
                var = sum((a / b - p) ** 2 for a, b in ks) / (m - 1)
                binv = sum(p * (1 - p) / b for _, b in ks) / m
                tau2 = max(var - binv, 0.000001)
            else:
                tau2 = 0.000001
            shrink[str(c)][str(x)] = [round(p, 6), round(tau2, 6)]

    return {
        "meta": {"from": meta_from, "to": meta_to, "races": n_races,
                 "cells": sum(len(v) for v in cells.values()),
                 "generated": jst_now(), "daysAdded": days_added},
        "base": base,
        "shrink": shrink,
        "cells": cells,
    }


def main():
    rows = read_base()
    max_hd = max((x["hd"] for x in rows), default="00000000")
    files = sorted(glob.glob(os.path.join(RESULTS, "*.json")))
    added_days = 0
    for p in files:
        hd = os.path.basename(p)[:8]
        if not (hd.isdigit() and len(hd) == 8) or hd <= max_hd:
            continue
        rows.extend(extract_from_results(p))
        added_days += 1
    if not rows:
        print("ERROR: no rows", file=sys.stderr)
        sys.exit(1)
    latest = max(x["hd"] for x in rows)
    lo = (datetime.strptime(latest, "%Y%m%d") - timedelta(days=WINDOW_DAYS - 1)).strftime("%Y%m%d")
    rows = [x for x in rows if x["hd"] >= lo]
    write_base(rows)
    j = build_json(rows, min(x["hd"] for x in rows), latest, added_days)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    s = json.dumps(j, ensure_ascii=False, separators=(",", ":"))
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
        f.write("\n")
    print("DAYS_ADDED=%d RACES=%d CELLS=%d BYTES=%d FROM=%s TO=%s" % (
        added_days, j["meta"]["races"], j["meta"]["cells"], len(s.encode("utf-8")) + 1,
        j["meta"]["from"], j["meta"]["to"]))


if __name__ == "__main__":
    main()
