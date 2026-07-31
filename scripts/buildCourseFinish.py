# -*- coding: utf-8 -*-
"""
buildCourseFinish.py

Kファイル由来の entries CSV から、場別 x 進入コース別の着順分布を集計する。

定義（固定）:
  分母 = shinnyu（進入コース）が 1-6 で取れる行 = 実際に走った艇
         shinnyu が空の行（K0/K1/L0 など出走なし）は分母から除外し件数を記録
  区分 = 1着 / 2着 / 3着 / 4着以下(04,05,06) / 失格等(F,S0,S1,S2,L1 など記号)
         引き算による派生値は作らない
  率   = 各区分 / n * 100（小数1位）。n < MIN_N のセルは率を null にする

出力: docs/data/courseFinish.json
"""

import csv
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

# ---- 設定 ----
IN_GLOB = r"C:\Users\USER\boatrace\localdata\kfiles\entries*.csv"
OUT_PATH = os.path.join("docs", "data", "courseFinish.json")
MIN_N = 100  # 母数ガード
JST = timezone(timedelta(hours=9))

CATS = ["c1", "c2", "c3", "c4plus", "dq"]
RATE_KEYS = {"c1": "r1", "c2": "r2", "c3": "r3", "c4plus": "r4plus", "dq": "rDq"}


def newCell():
    d = {"n": 0}
    for c in CATS:
        d[c] = 0
    return d


def hdToDate(hd):
    hd = hd.strip()
    if len(hd) != 6 or not hd.isdigit():
        return None
    return "20" + hd[0:2] + "-" + hd[2:4] + "-" + hd[4:6]


def classify(chaku):
    """着順文字列を区分に振り分ける。戻り値は CATS のいずれか、または None(不明)。"""
    v = chaku.strip()
    if v == "":
        return None
    if v.isdigit():
        n = int(v)
        if n == 1:
            return "c1"
        if n == 2:
            return "c2"
        if n == 3:
            return "c3"
        if n in (4, 5, 6):
            return "c4plus"
        return None
    # 数字以外はすべて失格等
    return "dq"


def addRate(cell):
    n = cell["n"]
    for c in CATS:
        k = RATE_KEYS[c]
        if n >= MIN_N:
            cell[k] = round(cell[c] * 100.0 / n, 1)
        else:
            cell[k] = None
    return cell


def main():
    files = sorted(glob.glob(IN_GLOB))
    if not files:
        print("ERROR: entries CSV が見つからない: " + IN_GLOB)
        sys.exit(1)

    venues = defaultdict(lambda: defaultdict(newCell))  # jcd -> course -> cell
    allc = defaultdict(newCell)  # course -> cell

    rowsTotal = 0
    rowsUsed = 0
    rowsSkippedNoCourse = 0
    rowsSkippedBadCourse = 0
    rowsSkippedUnknownChaku = 0
    symbolCount = defaultdict(int)
    minHd = None
    maxHd = None

    for path in files:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            need = ["hd", "jcd", "chaku", "shinnyu"]
            for col in need:
                if col not in reader.fieldnames:
                    print("ERROR: 列が無い: " + col + " / " + path)
                    sys.exit(1)
            for row in reader:
                rowsTotal += 1

                hd = (row.get("hd") or "").strip()
                if hd:
                    if minHd is None or hd < minHd:
                        minHd = hd
                    if maxHd is None or hd > maxHd:
                        maxHd = hd

                course = (row.get("shinnyu") or "").strip()
                if course == "":
                    rowsSkippedNoCourse += 1
                    continue
                if course not in ("1", "2", "3", "4", "5", "6"):
                    rowsSkippedBadCourse += 1
                    continue

                chaku = (row.get("chaku") or "").strip()
                cat = classify(chaku)
                if cat is None:
                    rowsSkippedUnknownChaku += 1
                    continue
                if cat == "dq":
                    symbolCount[chaku] += 1

                jcd = (row.get("jcd") or "").strip().zfill(2)
                if jcd == "" or jcd == "00":
                    rowsSkippedUnknownChaku += 1
                    continue

                venues[jcd][course]["n"] += 1
                venues[jcd][course][cat] += 1
                allc[course]["n"] += 1
                allc[course][cat] += 1
                rowsUsed += 1

    outVenues = {}
    for jcd in sorted(venues.keys()):
        outVenues[jcd] = {}
        for course in ["1", "2", "3", "4", "5", "6"]:
            cell = venues[jcd].get(course, newCell())
            outVenues[jcd][course] = addRate(cell)

    outAll = {}
    for course in ["1", "2", "3", "4", "5", "6"]:
        outAll[course] = addRate(allc.get(course, newCell()))

    meta = {
        "generated": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST"),
        "source": "mbrace 公式競走成績 Kファイル(kYYMMDD.lzh) 由来の entries CSV",
        "sourceUrl": "http://www1.mbrace.or.jp/od2/K/YYYYMM/kYYMMDD.lzh",
        "periodFrom": hdToDate(minHd) if minHd else None,
        "periodTo": hdToDate(maxHd) if maxHd else None,
        "files": len(files),
        "rowsTotal": rowsTotal,
        "rowsUsed": rowsUsed,
        "rowsSkippedNoCourse": rowsSkippedNoCourse,
        "rowsSkippedBadCourse": rowsSkippedBadCourse,
        "rowsSkippedUnknown": rowsSkippedUnknownChaku,
        "minN": MIN_N,
        "definition": {
            "denominator": "shinnyu(進入コース)が1-6で取れる行=実際に走った艇。shinnyu空(K0/K1/L0等)は分母から除外",
            "c1": "着順01",
            "c2": "着順02",
            "c3": "着順03",
            "c4plus": "着順04/05/06",
            "dq": "着順が数字でない行(F/S0/S1/S2/L1等)",
            "note": "率は各区分/n*100。派生値(引き算)は作らない",
        },
        "dqSymbols": dict(sorted(symbolCount.items())),
    }

    out = {"meta": meta, "all": outAll, "venues": outVenues}

    outDir = os.path.dirname(OUT_PATH)
    if outDir and not os.path.isdir(outDir):
        os.makedirs(outDir)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # ---- 自己検証（標準出力に出す。ここが全部OKでなければ結果を信用しない）----
    ok = True
    for jcd in outVenues:
        for course in outVenues[jcd]:
            cell = outVenues[jcd][course]
            s = sum(cell[c] for c in CATS)
            if s != cell["n"]:
                ok = False
                print("NG: 区分合計が n と不一致 jcd=" + jcd + " course=" + course)
    sumVenueN = sum(
        outVenues[j][c]["n"] for j in outVenues for c in outVenues[j]
    )
    sumAllN = sum(outAll[c]["n"] for c in outAll)
    if sumVenueN != sumAllN or sumAllN != rowsUsed:
        ok = False
        print("NG: 合計不一致 venues=" + str(sumVenueN) + " all=" + str(sumAllN) + " used=" + str(rowsUsed))

    print("files=" + str(len(files)))
    print("period=" + str(meta["periodFrom"]) + " .. " + str(meta["periodTo"]))
    print("rowsTotal=" + str(rowsTotal) + " used=" + str(rowsUsed)
          + " noCourse=" + str(rowsSkippedNoCourse)
          + " badCourse=" + str(rowsSkippedBadCourse)
          + " unknown=" + str(rowsSkippedUnknownChaku))
    print("venues=" + str(len(outVenues)))
    print("selfCheck=" + ("OK" if ok else "NG"))
    print("--- all (course: n / 1着% / 2着% / 3着% / 4着以下% / 失格等%) ---")
    for course in ["1", "2", "3", "4", "5", "6"]:
        c = outAll[course]
        print(course + "コース n=" + str(c["n"])
              + " 1着=" + str(c["r1"]) + "%"
              + " 2着=" + str(c["r2"]) + "%"
              + " 3着=" + str(c["r3"]) + "%"
              + " 4着以下=" + str(c["r4plus"]) + "%"
              + " 失格等=" + str(c["rDq"]) + "%")
    print("out=" + OUT_PATH)
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
