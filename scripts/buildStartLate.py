#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""選手別のスタート遅れ率を results/ から集計する。

「遅れ」＝本番STが LATE_TH 以上の走。公式の出遅れ（L）とは別物。
出力: docs/data/startLate.json
"""
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "results")
OUT_PATH = os.path.join(ROOT, "docs", "data", "startLate.json")

LATE_TH = 0.20
MIN_N = 20
ABSENT = 16
SOURCE = "results/*.json（公式レース結果・本番ST）"


def iter_boats(doc):
    """開催日 -> 結果[] -> 艇[] の階層をたどる。"""
    for race in doc.get("結果", []):
        for boat in race.get("艇", []):
            yield boat


def load_days():
    if not os.path.isdir(SRC_DIR):
        sys.exit("FATAL: results ディレクトリが無い: %s" % SRC_DIR)
    names = sorted(n for n in os.listdir(SRC_DIR) if n.endswith(".json"))
    if not names:
        sys.exit("FATAL: results に json が無い")
    return names


def main():
    names = load_days()
    total = defaultdict(lambda: [0, 0])
    per_course = defaultdict(lambda: [0, 0])
    base_course = defaultdict(lambda: [0, 0])
    st_list = defaultdict(list)
    days = 0

    for name in names:
        path = os.path.join(SRC_DIR, name)
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception as exc:
            print("skip %s (%s)" % (name, exc))
            continue
        if "結果" not in doc:
            continue
        days += 1
        for boat in iter_boats(doc):
            no = boat.get("登番")
            if no is None or boat.get("着") == ABSENT:
                continue
            st = boat.get("ST")
            course = boat.get("コース")
            if st is None or course is None:
                continue
            late = 1 if st >= LATE_TH else 0
            total[no][0] += 1
            total[no][1] += late
            per_course[(no, course)][0] += 1
            per_course[(no, course)][1] += late
            base_course[course][0] += 1
            base_course[course][1] += late
            st_list[no].append(st)

    racers = {}
    for no in sorted(total):
        n, late = total[no]
        if n < MIN_N:
            continue
        vals = sorted(st_list[no])
        rec = {"n": n, "late": late, "stMed": round(vals[len(vals) // 2], 2), "course": {}}
        for course in range(1, 7):
            cn, clate = per_course[(no, course)]
            if cn >= MIN_N:
                rec["course"][str(course)] = {"n": cn, "late": clate}
            elif cn > 0:
                rec["course"][str(course)] = {"n": cn}
        racers[str(no)] = rec

    base = {
        "全体": {
            "n": sum(v[0] for v in base_course.values()),
            "late": sum(v[1] for v in base_course.values()),
        },
        "コース": {
            str(c): {"n": base_course[c][0], "late": base_course[c][1]} for c in range(1, 7)
        },
    }

    doc = {
        "updated": names[-1][:8],
        "集計期間": "%s-%s" % (names[0][:8], names[-1][:8]),
        "日数": days,
        "母数ガード": MIN_N,
        "遅れの定義": "本番STが%.2f以上の走" % LATE_TH,
        "出典": SOURCE,
        "基準": base,
        "racers": racers,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(text)

    print("days=%d racers=%d bytes=%d" % (days, len(racers), len(text.encode("utf-8"))))
    print("base n=%d late=%d" % (base["全体"]["n"], base["全体"]["late"]))
    for c in range(1, 7):
        cn = base["コース"][str(c)]
        print("course%d n=%d late=%d (%.1f%%)" % (c, cn["n"], cn["late"], 100.0 * cn["late"] / cn["n"]))


if __name__ == "__main__":
    main()
