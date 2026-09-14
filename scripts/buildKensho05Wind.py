# -*- coding: utf-8 -*-
# buildKensho05Wind.py
# 検証05 作業6：①着外率を風で層別する（宿題1「大村の向かい風」2026-09-09 の回収を兼ねる）。
#
# 入力 : results/YYYYMMDD.json（DATE_FROM〜DATE_TO）／ docs/data/stadiumBearing.json（読むだけ）
# 出力 : analysis/kensho05/windCourse1.csv（Z1・Z2・Z3 を unit 列で区別）
#
# 定義（既存の定義をそのまま使う。変えない）
#   ①着外   … buildInSurvival.py と同一。「1着」「2着」「3着」が全て整数のとき、
#               3つの中に 1 が無ければ着外。揃わないレースは判定不能として分母から除く。
#   水面成分 … docs/results/index.html の windRel() と同一（facts.md の判定式）。
#               風向角＝(コード−1)×22.5、水面方位（2M→1M）との角度差 45°以下＝追い風・
#               135°以上＝向かい風・それ以外＝横風。風向コード17＝無風。
#   風速帯   … 0-1 / 2-3 / 4-5 / 6+（m）。風向コード17は風速帯に入れず「無風」の別枠。
#   ①イン限定 … results の 枠1 の「コース」==1（本番の進入。preview の展示進入は使わない）。
#   信頼区間 … Wilson 95%。n < MIN_N のセルは率・区間を空欄にし note に「n不足」。
#
# 使い方:
#   python scripts/buildKensho05Wind.py
import os
import io
import re
import csv
import sys
import json
import glob
import math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results")
BEARING_PATH = os.path.join(ROOT, "docs", "data", "stadiumBearing.json")
OUT_PATH = os.path.join(ROOT, "analysis", "kensho05", "windCourse1.csv")

DATE_FROM = "20250715"
DATE_TO = "20260913"      # 最終の確定日（20260914 は当日途中のため含めない）
MIN_N = 300
Z95 = 1.959963984540054
OMURA = "24"

BANDS = ["0-1", "2-3", "4-5", "6+"]
COMPS = ["追い風", "横風", "向かい風"]
NOWIND = "無風"
TOTAL = "計"


def stop(msg):
    print("STOP: " + msg)
    sys.exit(1)


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def waku1_out(r):
    """buildInSurvival.py と同一。着外=1 / 3着以内=0 / 判定不能=None"""
    top = [r.get("1着"), r.get("2着"), r.get("3着")]
    if not all(is_int(x) for x in top):
        return None
    return 0 if 1 in top else 1


def waku1_course(r):
    for b in r.get("艇", []) or []:
        if b.get("枠") == 1:
            return b.get("コース")
    return None


def component(bearing, code):
    """docs/results/index.html の windRel() と同一。"""
    if code == 17:
        return NOWIND
    d = (code - 1) * 22.5
    diff = abs((((d - bearing + 180) % 360) + 360) % 360 - 180)
    if diff <= 45:
        return "追い風"
    if diff >= 135:
        return "向かい風"
    return "横風"


def speed_band(ms):
    if ms <= 1:
        return "0-1"
    if ms <= 3:
        return "2-3"
    if ms <= 5:
        return "4-5"
    return "6+"


def wilson(k, n):
    p = k / n
    den = 1 + Z95 * Z95 / n
    c = (p + Z95 * Z95 / (2 * n)) / den
    h = Z95 * math.sqrt(p * (1 - p) / n + Z95 * Z95 / (4 * n * n)) / den
    return c - h, c + h


def cellstats(recs):
    """recs: [(out, in1)] → 全レース版とイン限定版の列"""
    out = []
    for sel in (recs, [t for t in recs if t[1]]):
        n = len(sel)
        k = sum(t[0] for t in sel)
        if n >= MIN_N:
            lo, hi = wilson(k, n)
            out.append([n, k, round(100.0 * k / n, 2), round(100.0 * lo, 2),
                        round(100.0 * hi, 2), ""])
        else:
            out.append([n, k, "", "", "", "n不足"])
    a, b = out
    diff = round(b[2] - a[2], 2) if a[2] != "" and b[2] != "" else ""
    return a + b + [diff]


def main():
    with io.open(BEARING_PATH, encoding="utf-8") as f:
        venues = json.load(f)["場"]
    bearing = {j: float(v["方位"]) for j, v in venues.items()}
    vname = {j: v["場名"] for j, v in venues.items()}

    files = sorted(p for p in glob.glob(os.path.join(RESULTS_DIR, "*.json"))
                   if re.match(r"^\d{8}\.json$", os.path.basename(p))
                   and DATE_FROM <= os.path.basename(p)[:8] <= DATE_TO)
    if not files:
        stop("results が読めない")

    recs = []           # (jcd, band, comp, out, in1)
    seen = set()
    skip = {"判定不能": 0, "風欠落": 0, "方位なし": 0}
    races = 0
    for p in files:
        hd = os.path.basename(p)[:8]
        with io.open(p, encoding="utf-8") as f:
            d = json.load(f)
        for r in d.get("結果", []) or []:
            races += 1
            jcd = str(r.get("場コード", "")).zfill(2)
            key = (hd, jcd, r.get("レース"))
            if key in seen:
                stop("同じレースが重複: %s" % (key,))
            seen.add(key)
            o = waku1_out(r)
            if o is None:
                skip["判定不能"] += 1
                continue
            code, ms = r.get("風向コード"), r.get("風速")
            if not is_int(code) or not 1 <= code <= 17 or not is_int(ms):
                skip["風欠落"] += 1
                continue
            if jcd not in bearing:
                skip["方位なし"] += 1
                continue
            comp = component(bearing[jcd], code)
            band = NOWIND if comp == NOWIND else speed_band(ms)
            recs.append((jcd, band, comp, o, waku1_course(r) == 1))

    def cross(unit, jcd, sub):
        rows = []

        def emit(band, comp, sel):
            rows.append([unit, jcd, vname.get(jcd, "全場"), band, comp]
                        + cellstats([(t[3], t[4]) for t in sel]))
        for band in BANDS:
            for comp in COMPS:
                emit(band, comp, [t for t in sub if t[1] == band and t[2] == comp])
        emit(NOWIND, NOWIND, [t for t in sub if t[2] == NOWIND])
        for band in BANDS:
            emit(band, TOTAL, [t for t in sub if t[1] == band])
        for comp in COMPS:
            emit(TOTAL, comp, [t for t in sub if t[2] == comp])
        emit(TOTAL, TOTAL, sub)
        return rows

    rows = cross("Z1", "全場", recs)
    rows += cross("Z2", OMURA, [t for t in recs if t[0] == OMURA])
    for jcd in sorted(bearing):
        sub = [t for t in recs if t[0] == jcd]
        for comp in COMPS + [NOWIND, TOTAL]:
            sel = sub if comp == TOTAL else [t for t in sub if t[2] == comp]
            rows.append(["Z3", jcd, vname[jcd], TOTAL, comp]
                        + cellstats([(t[3], t[4]) for t in sel]))

    header = ["unit", "jcd", "venue", "speedBand", "component",
              "n_all", "out_all", "rate_all", "ciLow_all", "ciHigh_all", "note_all",
              "n_in1", "out_in1", "rate_in1", "ciLow_in1", "ciHigh_in1", "note_in1",
              "diffPt_in1MinusAll"]
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)

    n = len(recs)
    nin = sum(t[4] for t in recs)
    om = [t for t in recs if t[0] == OMURA]
    print("期間 %s〜%s / ファイル %d / 全レース %d / 除外 %s"
          % (DATE_FROM, DATE_TO, len(files), races, skip))
    print("対象 全場 %d / 大村 %d / ①イン限定 全場 %d (%.2f%%) / 大村 %d (%.2f%%)"
          % (n, len(om), nin, 100.0 * nin / n, sum(t[4] for t in om),
             100.0 * sum(t[4] for t in om) / len(om)))
    share = {c: sum(1 for t in recs if t[2] == c) for c in COMPS + [NOWIND]}
    print("水面成分の構成比: " + " / ".join(
        "%s %.1f%%" % (c, 100.0 * v / n) for c, v in share.items()))
    print("全体の①着外率 %.2f%%" % (100.0 * sum(t[3] for t in recs) / n))
    short_all = sum(1 for r in rows if r[10] == "n不足")
    short_in = sum(1 for r in rows if r[16] == "n不足")
    print("セル数 %d / n不足 全レース版 %d / ①イン限定版 %d" % (len(rows), short_all, short_in))


if __name__ == "__main__":
    main()
