# -*- coding: utf-8 -*-
"""
buildCourseFinish.py

Kファイル由来の entries CSV から、場別の着順分布を2つの基準で集計する。

  byCourse … 進入コース(shinnyu)基準。実際に走ったコース。前づけが反映される。
  byWaku   … 枠番(waku)基準。艇番そのもの。前づけがあると進入コースとズレる。

母集団は両者で完全に同一（shinnyu と waku の両方が 1-6 で取れる行）。
基準だけを変えているので、2つの差はそのまま「前づけの影響」として読める。

区分（引き算による派生値は作らない）:
  1着 / 2着 / 3着 / 4着以下(04,05,06) / 失格等(F,S0,S1,S2,L1 等の記号)

率は 各区分 / n * 100（小数1位）。n < MIN_N のセルは率を null にする。

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

LANES = ["1", "2", "3", "4", "5", "6"]
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


def buildOut(venueAgg, allAgg):
    """集計辞書を出力形状に整える。"""
    outVenues = {}
    for jcd in sorted(venueAgg.keys()):
        outVenues[jcd] = {}
        for lane in LANES:
            outVenues[jcd][lane] = addRate(venueAgg[jcd].get(lane, newCell()))
    outAll = {}
    for lane in LANES:
        outAll[lane] = addRate(allAgg.get(lane, newCell()))
    return {"all": outAll, "venues": outVenues}


def checkSums(block, rowsUsed, label, errors):
    """区分合計と総数の整合を確認する。"""
    for jcd in block["venues"]:
        for lane in block["venues"][jcd]:
            cell = block["venues"][jcd][lane]
            if sum(cell[c] for c in CATS) != cell["n"]:
                errors.append("NG: 区分合計不一致 " + label + " jcd=" + jcd + " lane=" + lane)
    sumVenueN = sum(
        block["venues"][j][l]["n"] for j in block["venues"] for l in block["venues"][j]
    )
    sumAllN = sum(block["all"][l]["n"] for l in block["all"])
    if sumVenueN != sumAllN or sumAllN != rowsUsed:
        errors.append(
            "NG: 総数不一致 " + label
            + " venues=" + str(sumVenueN)
            + " all=" + str(sumAllN)
            + " used=" + str(rowsUsed)
        )


def main():
    files = sorted(glob.glob(IN_GLOB))
    if not files:
        print("ERROR: entries CSV が見つからない: " + IN_GLOB)
        sys.exit(1)

    courseVenue = defaultdict(lambda: defaultdict(newCell))
    courseAll = defaultdict(newCell)
    wakuVenue = defaultdict(lambda: defaultdict(newCell))
    wakuAll = defaultdict(newCell)

    rowsTotal = 0
    rowsUsed = 0
    rowsSkippedNoCourse = 0
    rowsSkippedBadCourse = 0
    rowsSkippedBadWaku = 0
    rowsSkippedUnknown = 0
    symbolCount = defaultdict(int)
    # 進入コースと枠番が一致しない行（前づけ・進入変化）の件数
    mismatch = 0
    mismatchVenue = defaultdict(int)
    minHd = None
    maxHd = None

    for path in files:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for col in ["hd", "jcd", "chaku", "shinnyu", "waku"]:
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
                if course not in LANES:
                    rowsSkippedBadCourse += 1
                    continue

                waku = (row.get("waku") or "").strip()
                if waku not in LANES:
                    rowsSkippedBadWaku += 1
                    continue

                chaku = (row.get("chaku") or "").strip()
                cat = classify(chaku)
                if cat is None:
                    rowsSkippedUnknown += 1
                    continue

                jcd = (row.get("jcd") or "").strip().zfill(2)
                if jcd == "" or jcd == "00":
                    rowsSkippedUnknown += 1
                    continue

                if cat == "dq":
                    symbolCount[chaku] += 1
                if course != waku:
                    mismatch += 1
                    mismatchVenue[jcd] += 1

                courseVenue[jcd][course]["n"] += 1
                courseVenue[jcd][course][cat] += 1
                courseAll[course]["n"] += 1
                courseAll[course][cat] += 1

                wakuVenue[jcd][waku]["n"] += 1
                wakuVenue[jcd][waku][cat] += 1
                wakuAll[waku]["n"] += 1
                wakuAll[waku][cat] += 1

                rowsUsed += 1

    byCourse = buildOut(courseVenue, courseAll)
    byWaku = buildOut(wakuVenue, wakuAll)

    # 場別の進入変化率（枠番と進入コースが違う艇の割合）
    shiftRate = {}
    for jcd in sorted(courseVenue.keys()):
        n = sum(courseVenue[jcd][l]["n"] for l in courseVenue[jcd])
        shiftRate[jcd] = {
            "n": n,
            "shifted": mismatchVenue.get(jcd, 0),
            "rate": round(mismatchVenue.get(jcd, 0) * 100.0 / n, 1) if n >= MIN_N else None,
        }

    meta = {
        "generated": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST"),
        "出典": "データ攻め",
        "source": "mbrace 公式競走成績 Kファイル(kYYMMDD.lzh) 由来の entries CSV",
        "sourceUrl": "http://www1.mbrace.or.jp/od2/K/YYYYMM/kYYMMDD.lzh",
        "periodFrom": hdToDate(minHd) if minHd else None,
        "periodTo": hdToDate(maxHd) if maxHd else None,
        "files": len(files),
        "rowsTotal": rowsTotal,
        "rowsUsed": rowsUsed,
        "rowsSkippedNoCourse": rowsSkippedNoCourse,
        "rowsSkippedBadCourse": rowsSkippedBadCourse,
        "rowsSkippedBadWaku": rowsSkippedBadWaku,
        "rowsSkippedUnknown": rowsSkippedUnknown,
        "shiftedRows": mismatch,
        "minN": MIN_N,
        "definition": {
            "denominator": "shinnyu(進入コース)と waku(枠番)の両方が1-6で取れる行。両基準で母集団は完全に同一",
            "byCourse": "進入コース(shinnyu)基準。実際に走ったコース",
            "byWaku": "枠番(waku)基準。艇番そのもの",
            "c1": "着順01",
            "c2": "着順02",
            "c3": "着順03",
            "c4plus": "着順04/05/06",
            "dq": "着順が数字でない行(F/S0/S1/S2/L1等)",
            "shiftRate": "枠番と進入コースが一致しなかった艇の割合(進入変化率)",
            "note": "率は各区分/n*100。派生値(引き算)は作らない",
        },
        "dqSymbols": dict(sorted(symbolCount.items())),
    }

    out = {
        "meta": meta,
        "byCourse": byCourse,
        "byWaku": byWaku,
        "shiftRate": shiftRate,
    }

    outDir = os.path.dirname(OUT_PATH)
    if outDir and not os.path.isdir(outDir):
        os.makedirs(outDir)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # ---- 自己検証（ここが全部OKでなければ結果を信用しない）----
    errors = []
    checkSums(byCourse, rowsUsed, "byCourse", errors)
    checkSums(byWaku, rowsUsed, "byWaku", errors)
    for e in errors:
        print(e)
    ok = len(errors) == 0

    print("files=" + str(len(files)))
    print("period=" + str(meta["periodFrom"]) + " .. " + str(meta["periodTo"]))
    print("rowsTotal=" + str(rowsTotal) + " used=" + str(rowsUsed)
          + " noCourse=" + str(rowsSkippedNoCourse)
          + " badCourse=" + str(rowsSkippedBadCourse)
          + " badWaku=" + str(rowsSkippedBadWaku)
          + " unknown=" + str(rowsSkippedUnknown))
    print("venues=" + str(len(byCourse["venues"])))
    print("shiftedRows=" + str(mismatch)
          + " (" + str(round(mismatch * 100.0 / rowsUsed, 2)) + "%)")
    print("selfCheck=" + ("OK" if ok else "NG"))

    print("--- all byCourse (lane: n / 1着% / 2着% / 3着% / 4着以下% / 失格等%) ---")
    for lane in LANES:
        c = byCourse["all"][lane]
        print(lane + " n=" + str(c["n"]) + " " + str(c["r1"]) + " " + str(c["r2"])
              + " " + str(c["r3"]) + " " + str(c["r4plus"]) + " " + str(c["rDq"]))
    print("--- all byWaku (lane: n / 1着% / 2着% / 3着% / 4着以下% / 失格等%) ---")
    for lane in LANES:
        c = byWaku["all"][lane]
        print(lane + " n=" + str(c["n"]) + " " + str(c["r1"]) + " " + str(c["r2"])
              + " " + str(c["r3"]) + " " + str(c["r4plus"]) + " " + str(c["rDq"]))

    print("--- venue compare (jcd / course1-1chaku% / waku1-1chaku% / diff / shiftRate%) ---")
    for jcd in sorted(byCourse["venues"].keys()):
        a = byCourse["venues"][jcd]["1"]["r1"]
        b = byWaku["venues"][jcd]["1"]["r1"]
        diff = round(a - b, 1) if (a is not None and b is not None) else None
        print(jcd + " " + str(a) + " " + str(b) + " " + str(diff)
              + " " + str(shiftRate[jcd]["rate"]))

    print("out=" + OUT_PATH)
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
