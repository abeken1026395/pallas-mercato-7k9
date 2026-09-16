#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""選手×枠番の成績（1着・2連対・3連対）を期間別に集計する。

正本  : data/wakuStats/base.csv   列 hd,toban,waku,chaku（1走1行・全レース）
入力  : results/YYYYMMDD.json     正本の最大hdより新しい日だけ読む
出力  : docs/data/wakuStats.json  回数のみ（率は表示側で計算する）

期間は 2ヶ月/3ヶ月/半年/1年/2年 の5本。いずれも最新日から遡る。
着コードの表記ゆれ（Kファイル由来は "01"、results 由来は "1"）は読み込み時に正規化する。
"""
import csv
import glob
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "data", "wakuStats", "base.csv")
OUT = os.path.join(ROOT, "docs", "data", "wakuStats.json")
RESULTS = os.path.join(ROOT, "results")
COLS = ["hd", "toban", "waku", "chaku"]
# (キー, 遡る日数)。最長が正本の保持期間になる
PERIODS = [("2m", 61), ("3m", 92), ("6m", 183), ("1y", 365), ("2y", 730)]
WINDOW_DAYS = max(d for _, d in PERIODS)


def jst_now():
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")


# 欠場。Kファイルは K0/K1、results は 16。走っていないので分母から外す
# （racerCourseStats.json と同じ扱い）。失格・出遅れ（F / S0-S2 / L0-L1 / 7〜15）は
# 走った上で入着できなかったものなので分母に残す。
ABSENT = ("K0", "K1", "16")


def norm_chaku(v):
    """着コードの表記ゆれを吸収する。Kファイルは "01".."06"、results は 1..6。
    失格・欠場等（S0/F/L0 や 7〜16）はそのまま返す。"""
    v = str(v).strip()
    return v.lstrip("0") or v


def is_absent(ch):
    return ch in ABSENT


def read_base():
    if not os.path.exists(BASE):
        return []
    with io.open(BASE, "r", encoding="utf-8", newline="") as f:
        rows = []
        for x in csv.DictReader(f):
            rows.append({
                "hd": str(x.get("hd")).strip(),
                "toban": str(x.get("toban")).strip(),
                "waku": str(x.get("waku")).strip(),
                "chaku": norm_chaku(x.get("chaku")),
            })
        return rows


def write_base(rows):
    rows.sort(key=lambda x: (x["hd"], x["toban"], x["waku"]))
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
        for b in r.get("艇") or []:
            waku = b.get("枠")
            toban = b.get("登番")
            if not waku or not toban:
                continue
            ch = b.get("着")
            out.append({
                "hd": hd, "toban": str(toban), "waku": str(int(waku)),
                "chaku": norm_chaku(ch if ch is not None else ""),
            })
    return out


def build_json(rows, latest):
    # 期間ごとの下限日
    los = []
    for key, days in PERIODS:
        lo = (datetime.strptime(latest, "%Y%m%d") - timedelta(days=days - 1)).strftime("%Y%m%d")
        los.append((key, lo))

    # cells[toban][waku] = [[n,c1,c2,c3] x 5期間]
    cells = {}
    # base[期間][枠] = [n,c1,c2,c3]（枠番別の全体平均。読者が比較に使う基準行。
    # 全艇合計にすると必ず 1/6・2/6・3/6 になり比較対象にならないため枠番別に持つ）
    totals = [{str(w): [0, 0, 0, 0] for w in range(1, 7)} for _ in PERIODS]
    for x in rows:
        hd = x["hd"]
        ch = x["chaku"]
        if is_absent(ch):
            continue
        one = 1 if ch == "1" else 0
        two = 1 if ch in ("1", "2") else 0
        three = 1 if ch in ("1", "2", "3") else 0
        arr = cells.setdefault(x["toban"], {}).setdefault(x["waku"], [[0, 0, 0, 0] for _ in PERIODS])
        for i, (_, lo) in enumerate(los):
            if hd >= lo:
                arr[i][0] += 1
                arr[i][1] += one
                arr[i][2] += two
                arr[i][3] += three
                tw = totals[i].get(x["waku"])
                if tw is not None:
                    tw[0] += 1
                    tw[1] += one
                    tw[2] += two
                    tw[3] += three

    return {
        "meta": {
            "from": min(x["hd"] for x in rows), "to": latest,
            "periods": [k for k, _ in PERIODS],
            "periodDays": {k: d for k, d in PERIODS},
            "runs": len(rows),
            "cells": sum(len(v) for v in cells.values()),
            "generated": jst_now(),
        },
        "base": totals,
        "cells": cells,
    }


def main():
    rows = read_base()
    max_hd = max((x["hd"] for x in rows), default="00000000")
    # 最新日は「途中版の results」を取り込んでいる可能性があるため、その日を捨てて読み直す。
    # hd <= max_hd を素通しにすると、当日の残りのレースが永久に追加されない。
    if max_hd != "00000000":
        rows = [x for x in rows if x["hd"] < max_hd]
    added = 0
    for p in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        hd = os.path.basename(p)[:8]
        if not (hd.isdigit() and len(hd) == 8) or hd < max_hd:
            continue
        rows.extend(extract_from_results(p))
        added += 1
    if not rows:
        print("ERROR: no rows", file=sys.stderr)
        sys.exit(1)
    latest = max(x["hd"] for x in rows)
    lo = (datetime.strptime(latest, "%Y%m%d") - timedelta(days=WINDOW_DAYS - 1)).strftime("%Y%m%d")
    rows = [x for x in rows if x["hd"] >= lo]
    write_base(rows)
    j = build_json(rows, latest)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    s = json.dumps(j, ensure_ascii=False, separators=(",", ":"))
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
        f.write("\n")
    print("DAYS_ADDED=%d RUNS=%d CELLS=%d BYTES=%d FROM=%s TO=%s" % (
        added, j["meta"]["runs"], j["meta"]["cells"], len(s.encode("utf-8")) + 1,
        j["meta"]["from"], j["meta"]["to"]))


if __name__ == "__main__":
    main()
