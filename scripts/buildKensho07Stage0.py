# -*- coding: utf-8 -*-
# buildKensho07Stage0.py
# 検証07「冬はイン、夏はまくり」は本当か ── stage0：分母と欠損率の確認。
#
# 省メモリ版。1レースぶんだけを持って流し、月ごとの数え上げだけを残す。
# 年ごとに分けて実行し、最後に merge でまとめる。途中で落ちても年単位でやり直せる。
#
# 使い方（この順・PARTS は実行のたびに追記される）
#   py scripts\buildKensho07Stage0.py year 2016
#   ...（2026 まで）
#   py scripts\buildKensho07Stage0.py results
#   py scripts\buildKensho07Stage0.py merge
#
# 入力A : Kファイル kYYMMDD.lzh（KFILES_DIR・読むだけ）。2016-11-01〜。
# 入力B : results/YYYYMMDD.json（読むだけ）。気温・水温の有無だけを見る。
# 中間  : PARTS_DIR（リポジトリの外）に年ごとのJSON。コミットしない。
# 出力  : analysis/kensho07/stage0.json ／ analysis/kensho07/stage0Months.csv
#
# 結論は出さない。分母ゲートが外れたら何も書かず終了コード1で止まる。
import os
import re
import io
import sys
import csv
import glob
import json
import math
import shutil
import tempfile
import subprocess
from collections import Counter

KFILES_DIR = r"C:\Users\USER\boatrace\data\kfiles"
PARTS_DIR = r"C:\Users\USER\kensho07parts"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results")
OUTDIR = os.path.join(ROOT, "analysis", "kensho07")
K_FROM = "20161101"
K_TO = "20260831"
RESULTS_FROM = "20250715"
RESULTS_TO = "20260918"
BSDTAR = shutil.which("bsdtar") or shutil.which("tar") or "tar"

KIMARITE6 = ["\u9003\u3052", "\u5dee\u3057", "\u307e\u304f\u308a",
             "\u307e\u304f\u308a\u5dee\u3057", "\u629c\u304d", "\u6075\u307e\u308c"]
TEMP_BINS = [(-99, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 35), (35, 99)]
MCOLS = ["k_races", "k_entries", "k_parseFail", "k_kimariteNot6", "k_windMissing",
         "k_c1Races", "k_c1Win", "k_c1UnknownRaces", "k_c1StMissing", "k_winRaceTimeMissing",
         "k_nige", "k_sashi", "k_makuri", "k_makurizashi", "k_nuki", "k_megumare"]
KIMCOL = {KIMARITE6[0]: "k_nige", KIMARITE6[1]: "k_sashi", KIMARITE6[2]: "k_makuri",
          KIMARITE6[3]: "k_makurizashi", KIMARITE6[4]: "k_nuki", KIMARITE6[5]: "k_megumare"}

KBGN_RE = re.compile(r"^(\d{2})KBGN")
KEND_RE = re.compile(r"^(\d{2})KEND")
HEAD_RE = re.compile(
    r"^\s+(\d+)R[\s\u3000]+(.+?)[\s\u3000]+H(\d+)m"
    r"[\s\u3000]+([^\s\u3000]+)[\s\u3000]+\u98a8[\s\u3000]+([^\s\u3000]+)[\s\u3000]+(\d+)m"
    r"[\s\u3000]+\u6ce2[\s\u3000]+(\d+)cm")
ENTRY_RE = re.compile(
    r"^\s*(\S+)[\s\u3000]+(\d)[\s\u3000]+(\d{4})[\s\u3000]+(.+?)"
    r"[\s\u3000]+(\d+)[\s\u3000]+(\d+)[\s\u3000]+(\d+\.\d{2})"
    r"[\s\u3000]+(\d)[\s\u3000]+(\S+)[\s\u3000]+(.+?)[\s\u3000]*$")
ENTRY_RE2 = re.compile(
    r"^\s*(\S+)[\s\u3000]+(\d)[\s\u3000]+(\d{4})[\s\u3000]+(.+?)"
    r"[\s\u3000]+(\d+)[\s\u3000]+(\d+)[\s\u3000]+(.*)$")
ENTRY_HINT = re.compile(r"^\s*(\d|S|F|L|K|\u6b20|\u5931|\u59a8|\u8ee2)")
CHAKU1_RE = re.compile(r"^0?1$")
NUM_RE = re.compile(r"^0?\d$")
TOKS_RE = re.compile(r"[\s\u3000]+")


def stop(msg):
    print("STOP: " + msg)
    sys.exit(1)


def unlzh(path):
    try:
        import lhafile
    except ImportError:
        pass
    else:
        arc = lhafile.Lhafile(path)
        names = arc.namelist()
        return arc.read(names[0]) if names else b""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([BSDTAR, "-xf", path, "-C", td], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        txts = glob.glob(os.path.join(td, "*.TXT")) + glob.glob(os.path.join(td, "*.txt"))
        if not txts:
            return b""
        with open(txts[0], "rb") as f:
            return f.read()


def decode_kfile(path):
    if path.lower().endswith(".lzh"):
        raw = unlzh(path)
    else:
        with open(path, "rb") as f:
            raw = f.read()
    return raw.decode("shift_jis", errors="replace")


def file_hd(path):
    m = re.search(r"[kK](\d{2})(\d{2})(\d{2})", os.path.basename(path))
    return "20{}{}{}".format(m.group(1), m.group(2), m.group(3)) if m else ""


def chaku_class(c):
    if NUM_RE.match(c):
        return "numeric"
    if c[:1] == "F":
        return "F"
    if c[:1] == "L":
        return "L"
    if c[:1] == "S":
        return "S"
    if c[:1] == "K" or c[:1] == "\u6b20":
        return "K"
    return "other"


def blank_month():
    return dict((c, 0) for c in MCOLS)


def flush_race(acc, mo, head, boats, kimcnt, chakucnt):
    """1レースぶんを月の数え上げに足す。boats は (chaku, shinnyu, st, raceTime) のリスト。"""
    m = acc.setdefault(mo, blank_month())
    m["k_races"] += 1
    m["k_entries"] += len(boats)
    kim = head[3]
    kimcnt[kim] += 1
    if kim in KIMCOL:
        m[KIMCOL[kim]] += 1
    else:
        m["k_kimariteNot6"] += 1
    if head[1] == "" or head[2] is None:
        m["k_windMissing"] += 1
    c1 = [b for b in boats if b[1] == 1]
    for b in boats:
        chakucnt[chaku_class(b[0])] += 1
    if not c1:
        m["k_c1UnknownRaces"] += 1
    else:
        m["k_c1Races"] += 1
        if any(CHAKU1_RE.match(b[0]) for b in c1):
            m["k_c1Win"] += 1
        if all(b[2] == "" for b in c1):
            m["k_c1StMissing"] += 1
    win = [b for b in boats if CHAKU1_RE.match(b[0])]
    if not win or all(b[3] == "" for b in win):
        m["k_winRaceTimeMissing"] += 1


def scan_day(text, hd, acc, kimcnt, chakucnt):
    """1日ぶんを流す。レース単位でだけ保持する。戻り値は (レース数, 解析失敗行数)。"""
    mo = hd[:6]
    jcd = None
    head = None          # (rno, windDir, waveCm, kimarite)
    boats = []
    races = 0
    fails = 0

    def close():
        if head is not None:
            flush_race(acc, mo, head, boats, kimcnt, chakucnt)

    for ln in text.split("\n"):
        m = KBGN_RE.match(ln)
        if m:
            close()
            head = None
            boats = []
            jcd = m.group(1)
            continue
        if KEND_RE.match(ln):
            close()
            head = None
            boats = []
            jcd = None
            continue
        if jcd is None:
            continue
        hm = HEAD_RE.match(ln)
        if hm:
            close()
            boats = []
            head = [int(hm.group(1)), hm.group(5), int(hm.group(7)), ""]
            races += 1
            continue
        if head is None:
            continue
        if "\u767b\u756a" in ln and "\u9078" in ln:
            t = TOKS_RE.split(ln.strip())
            head[3] = t[-1] if t else ""
            continue
        if "---" in ln:
            continue
        em = ENTRY_RE.match(ln)
        if em:
            rt = em.group(10).strip()
            if not re.search(r"\d", rt):
                rt = ""
            boats.append((em.group(1), int(em.group(8)), em.group(9), rt))
            continue
        if ENTRY_HINT.match(ln):
            em2 = ENTRY_RE2.match(ln)
            if em2:
                boats.append((em2.group(1), None, "", ""))
                continue
            if ln.strip() and "\u767b\u756a" not in ln:
                fails += 1
    close()
    return races, fails


def part_path(name):
    return os.path.join(PARTS_DIR, name)


def run_year(year):
    os.makedirs(PARTS_DIR, exist_ok=True)
    files = sorted(p for p in glob.glob(os.path.join(KFILES_DIR, "*.lzh"))
                   if K_FROM <= file_hd(p) <= K_TO and file_hd(p)[:4] == year)
    if not files:
        stop("%s のKファイルが0件" % year)
    acc = {}
    kimcnt = Counter()
    chakucnt = Counter()
    bad = []
    small = []
    nfail = 0
    for i, p in enumerate(files):
        hd = file_hd(p)
        try:
            text = decode_kfile(p)
        except Exception as e:
            bad.append([hd, "decode: %s" % e])
            continue
        races, fails = scan_day(text, hd, acc, kimcnt, chakucnt)
        nfail += fails
        if races == 0:
            bad.append([hd, "no races"])
            continue
        if races < 24:
            small.append([hd, races])
        acc.setdefault(hd[:6], blank_month())["k_parseFail"] += fails
        if (i + 1) % 100 == 0:
            print("  %s %d/%d" % (year, i + 1, len(files)))
            sys.stdout.flush()
    out = {"year": year, "files": len(files), "months": acc,
           "kimarite": dict(kimcnt), "chaku": dict(chakucnt),
           "badDays": bad, "daysUnder24Races": small, "parseFail": nfail}
    with open(part_path("k%s.json" % year), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False)
    print("OK year=%s files=%d races=%d bad=%d"
          % (year, len(files), sum(v["k_races"] for v in acc.values()), len(bad)))


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def temp_bin(v):
    for lo, hi in TEMP_BINS:
        if lo <= v < hi:
            return "{}-{}".format(lo, hi)
    return "?"


def run_results():
    os.makedirs(PARTS_DIR, exist_ok=True)
    rfiles = sorted(p for p in glob.glob(os.path.join(RESULTS_DIR, "*.json"))
                    if re.match(r"^\d{8}\.json$", os.path.basename(p))
                    and RESULTS_FROM <= os.path.basename(p)[:8] <= RESULTS_TO)
    if len(rfiles) < 300:
        stop("results が少なすぎる: %d" % len(rfiles))
    months = {}
    air = Counter()
    water = Counter()
    total = 0
    for p in rfiles:
        mo = os.path.basename(p)[:6]
        with io.open(p, encoding="utf-8") as f:
            d = json.load(f)
        m = months.setdefault(mo, {"r_races": 0, "r_airMissing": 0, "r_waterMissing": 0})
        for r in d.get("\u7d50\u679c", []) or []:
            total += 1
            m["r_races"] += 1
            a = r.get("\u6c17\u6e29")
            w = r.get("\u6c34\u6e29")
            if is_num(a):
                air[temp_bin(a)] += 1
            else:
                m["r_airMissing"] += 1
            if is_num(w):
                water[temp_bin(w)] += 1
            else:
                m["r_waterMissing"] += 1
        del d
    out = {"files": len(rfiles), "races": total, "months": months,
           "airBins": dict(air), "waterBins": dict(water)}
    with open(part_path("results.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False)
    print("OK results files=%d races=%d" % (len(rfiles), total))


def merge():
    kparts = sorted(glob.glob(part_path("k*.json")))
    if len(kparts) < 11:
        stop("年ごとの中間ファイルが足りない: %d（2016〜2026の11本が要る）" % len(kparts))
    rp = part_path("results.json")
    if not os.path.exists(rp):
        stop("results の中間ファイルが無い")
    acc = {}
    kimcnt = Counter()
    chakucnt = Counter()
    bad = []
    small = []
    kfiles = 0
    for p in kparts:
        with io.open(p, encoding="utf-8") as f:
            d = json.load(f)
        kfiles += d["files"]
        for mo, v in d["months"].items():
            m = acc.setdefault(mo, blank_month())
            for c in MCOLS:
                m[c] += v.get(c, 0)
        kimcnt.update(d["kimarite"])
        chakucnt.update(d["chaku"])
        bad += d["badDays"]
        small += d["daysUnder24Races"]
    with io.open(rp, encoding="utf-8") as f:
        rd = json.load(f)

    total_races = sum(v["k_races"] for v in acc.values())
    total_entries = sum(v["k_entries"] for v in acc.values())
    if kfiles < 3500:
        stop("kfiles が少なすぎる: %d" % kfiles)
    if len(bad) > 5:
        stop("読めない日が %d 日ある" % len(bad))
    if not (520000 <= total_races <= 570000):
        stop("Kファイルのレース総数が想定外: %d" % total_races)
    if len(small) > 40:
        stop("1日あたりレース数が24未満の日が多すぎる: %d" % len(small))

    months = sorted(set(acc) | set(rd["months"]))
    rows = []
    for mo in months:
        m = acc.get(mo, blank_month())
        r = rd["months"].get(mo, {"r_races": 0, "r_airMissing": 0, "r_waterMissing": 0})
        c1n = m["k_c1Races"]
        row = {"month": mo}
        for c in MCOLS:
            row[c] = m[c]
        row["k_c1WinRateRaw"] = round(100.0 * m["k_c1Win"] / c1n, 2) if c1n else ""
        row["r_races"] = r["r_races"]
        row["r_airMissing"] = r["r_airMissing"]
        row["r_waterMissing"] = r["r_waterMissing"]
        rows.append(row)

    summary = {
        "stage": 0,
        "purpose": "\u5206\u6bcd\u3068\u6b20\u640d\u7387\u306e\u78ba\u8a8d\u3002\u7d50\u8ad6\u306f\u51fa\u3055\u306a\u3044",
        "kfiles": {"dir": KFILES_DIR, "from": K_FROM, "to": K_TO, "files": kfiles,
                   "races": total_races, "entries": total_entries,
                   "badDays": bad, "daysUnder24Races": small[:50],
                   "chakuClasses": dict(chakucnt),
                   "kimariteValues": dict(kimcnt.most_common())},
        "results": {"dir": "results", "from": RESULTS_FROM, "to": RESULTS_TO,
                    "files": rd["files"], "races": rd["races"],
                    "airMissing": sum(v["r_airMissing"] for v in rd["months"].values()),
                    "waterMissing": sum(v["r_waterMissing"] for v in rd["months"].values()),
                    "airBins": rd["airBins"], "waterBins": rd["waterBins"]},
        "note": "\u6c17\u6e29\u30fb\u6c34\u6e29\u306f results\uff082025-07-15\u301c\uff09\u306b\u3057\u304b\u7121\u3044\u3002K\u30d5\u30a1\u30a4\u30eb\u306f\u5929\u5019\u30fb\u98a8\u5411\u30fb\u98a8\u901f\u30fb\u6ce2\u9ad8\u306e\u307f",
    }
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "stage0.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"summary": summary, "months": rows}, f, ensure_ascii=False, indent=1)
    cols = ["month"] + MCOLS + ["k_c1WinRateRaw", "r_races", "r_airMissing", "r_waterMissing"]
    with open(os.path.join(OUTDIR, "stage0Months.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("OK merge kfiles=%d races=%d entries=%d results_races=%d months=%d"
          % (kfiles, total_races, total_entries, rd["races"], len(rows)))
    print("kimarite=%s" % json.dumps(dict(kimcnt.most_common(12)), ensure_ascii=True))
    print("chaku=%s" % json.dumps(dict(chakucnt), ensure_ascii=True))


def main():
    if len(sys.argv) < 2:
        stop("mode が無い（year <YYYY> / results / merge）")
    mode = sys.argv[1]
    if mode == "year":
        if len(sys.argv) < 3:
            stop("year の引数が無い")
        for y in sys.argv[2:]:
            run_year(y)
    elif mode == "results":
        run_results()
    elif mode == "merge":
        merge()
    else:
        stop("不明な mode: %s" % mode)


if __name__ == "__main__":
    main()
