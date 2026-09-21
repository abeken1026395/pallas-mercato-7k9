# -*- coding: utf-8 -*-
# buildKensho07Stage1.py
# 検証07「冬はイン、夏はまくり」は本当か -- stage1：冬夏差の統制と置換検定。
#
# 使い方（この順）
#   py scripts\buildKensho07Stage1.py rows 2016   （2016 から 2026 まで1年ずつ）
#   py scripts\buildKensho07Stage1.py temps
#   py scripts\buildKensho07Stage1.py analyze
#
# rows    : Kファイルを1レースずつ流し、1レース1行のCSVを PARTS_DIR に年ごとに書く（リポジトリの外）
# temps   : results の気温・水温を 1レース1行で PARTS_DIR に書く
# analyze : 年の順に流し、選手の直前12か月の1着率で強さを出し、層ごとに数え上げて検定する
# 出力    : analysis/kensho07/stage1.json
#
# 季節の定義：冬＝12・1・2月、夏＝7・8月。季節年 SY は 12月だけ翌年に繰り入れる。
# 層：場 x 季節年 x レース区分 x 1コース選手の強さ x 外5艇の強さ
# 検定：層の中で季節ラベルを入れ替える置換（超幾何で厳密に同値）。1,000回。
#       層ごとに splitmix64 で種を作るので、層の分け方で結果が変わらない（自己照合する）。
# グレード（SG・G1）はKファイルに無いので層に入れない。級別の代わりに直前12か月の1着率を使う。
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
from collections import Counter, defaultdict

KFILES_DIR = r"C:\Users\USER\boatrace\data\kfiles"
PARTS_DIR = r"C:\Users\USER\kensho07parts"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results")
OUTDIR = os.path.join(ROOT, "analysis", "kensho07")
K_FROM = "20161101"
K_TO = "20260831"
RESULTS_FROM = "20250715"
RESULTS_TO = "20260918"
YEARS = [str(y) for y in range(2016, 2027)]
SEED = 20260920
NPERM = 1000
BSDTAR = shutil.which("bsdtar") or shutil.which("tar") or "tar"

KIM6 = ["\u9003\u3052", "\u5dee\u3057", "\u307e\u304f\u308a",
        "\u307e\u304f\u308a\u5dee\u3057", "\u629c\u304d", "\u6075\u307e\u308c"]
KIMKEY = {KIM6[0]: "nige", KIM6[1]: "sashi", KIM6[2]: "makuri",
          KIM6[3]: "makurizashi", KIM6[4]: "nuki", KIM6[5]: "megumare"}
WINTER = (12, 1, 2)
SUMMER = (7, 8)
ROWCOLS = ["hd", "jcd", "rno", "rclass", "windMps", "waveCm", "kim", "winCourse",
           "c1st", "winRt", "t1", "t2", "t3", "t4", "t5", "t6"]
MIN_STARTS = 30
PAIR_MIN = 10
SOLO_MIN = 30
CELL_MIN = 300

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
CHAKU1_RE = re.compile(r"^0?1$")
ST_RE = re.compile(r"^\d?\.\d+$")
RT_RE = re.compile(r"^(\d)\.(\d{2})\.(\d)$")
TOKS_RE = re.compile(r"[\s\u3000]+")
M64 = (1 << 64) - 1


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


def rclass_of(name):
    if "\u6e96\u512a" in name:
        return "semi"
    if "\u512a\u52dd" in name:
        return "final"
    if "\u4e88\u9078" in name or "\u4e00\u822c" in name:
        return "heat"
    return "special"


def race_row(hd, jcd, head, boats):
    """1レース → CSV の1行（dict）。成立しないレースは None。"""
    kim = head[4]
    if kim not in KIMKEY:
        return None
    t = {}
    win_course = 0
    c1st = ""
    win_rt = ""
    for chaku, shin, toban, st, rt in boats:
        if shin is None:
            continue
        t[shin] = toban
        if shin == 1 and ST_RE.match(st):
            c1st = st
        if CHAKU1_RE.match(chaku):
            win_course = shin
            m = RT_RE.match(rt)
            if m:
                win_rt = "%.1f" % (60 * int(m.group(1)) + int(m.group(2)) + int(m.group(3)) / 10.0)
    if 1 not in t or win_course == 0:
        return None
    row = {"hd": hd, "jcd": jcd, "rno": head[0], "rclass": head[1],
           "windMps": head[2], "waveCm": head[3], "kim": KIMKEY[kim],
           "winCourse": win_course, "c1st": c1st, "winRt": win_rt}
    for c in range(1, 7):
        row["t%d" % c] = t.get(c, "")
    return row


def scan_day(text, hd, w):
    """1日ぶんを流して CSV に書く。戻り値は (書いた行数, 捨てたレース数)。"""
    jcd = None
    head = None      # [rno, rclass, windMps, waveCm, kimarite]
    boats = []
    n_ok = 0
    n_drop = 0

    def close():
        nonlocal n_ok, n_drop
        if head is None:
            return
        r = race_row(hd, jcd, head, boats)
        if r is None:
            n_drop += 1
        else:
            w.writerow(r)
            n_ok += 1

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
            head = [int(hm.group(1)), rclass_of(hm.group(2)), int(hm.group(6)),
                    int(hm.group(7)), ""]
            continue
        if head is None:
            continue
        if "\u767b\u756a" in ln and "\u9078" in ln:
            tk = TOKS_RE.split(ln.strip())
            head[4] = tk[-1] if tk else ""
            continue
        em = ENTRY_RE.match(ln)
        if em:
            rt = em.group(10).strip()
            boats.append((em.group(1), int(em.group(8)), em.group(3), em.group(9), rt))
    close()
    return n_ok, n_drop


def run_rows(year):
    os.makedirs(PARTS_DIR, exist_ok=True)
    files = sorted(p for p in glob.glob(os.path.join(KFILES_DIR, "*.lzh"))
                   if K_FROM <= file_hd(p) <= K_TO and file_hd(p)[:4] == year)
    if not files:
        stop("%s のKファイルが0件" % year)
    out = os.path.join(PARTS_DIR, "s1r%s.csv" % year)
    n_ok = 0
    n_drop = 0
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ROWCOLS)
        w.writeheader()
        for i, p in enumerate(files):
            hd = file_hd(p)
            try:
                text = decode_kfile(p)
            except Exception as e:
                stop("decode 失敗 %s: %s" % (hd, e))
            a, b = scan_day(text, hd, w)
            n_ok += a
            n_drop += b
            if (i + 1) % 100 == 0:
                print("  %s %d/%d" % (year, i + 1, len(files)))
                sys.stdout.flush()
    print("OK rows year=%s files=%d races=%d dropped=%d" % (year, len(files), n_ok, n_drop))


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def run_temps():
    os.makedirs(PARTS_DIR, exist_ok=True)
    rfiles = sorted(p for p in glob.glob(os.path.join(RESULTS_DIR, "*.json"))
                    if re.match(r"^\d{8}\.json$", os.path.basename(p))
                    and RESULTS_FROM <= os.path.basename(p)[:8] <= RESULTS_TO)
    if len(rfiles) < 300:
        stop("results が少なすぎる: %d" % len(rfiles))
    n = 0
    with open(os.path.join(PARTS_DIR, "s1temps.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hd", "jcd", "rno", "air", "water"])
        for p in rfiles:
            hd = os.path.basename(p)[:8]
            with io.open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            for r in d.get("\u7d50\u679c", []) or []:
                a = r.get("\u6c17\u6e29")
                wt = r.get("\u6c34\u6e29")
                jcd = str(r.get("\u5834\u30b3\u30fc\u30c9", ""))
                rno = str(r.get("\u30ec\u30fc\u30b9", "")).rstrip("R")
                if not (is_num(a) and is_num(wt) and jcd and rno.isdigit()):
                    continue
                w.writerow([hd, jcd, int(rno), a, wt])
                n += 1
            del d
    print("OK temps files=%d races=%d" % (len(rfiles), n))


def splitmix64(x):
    x = (x + 0x9E3779B97F4A7C15) & M64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
    return z ^ (z >> 31)


def fnv1a64(s):
    h = 0xCBF29CE484222325
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x100000001B3) & M64
    return h


def month_index(hd):
    return int(hd[:4]) * 12 + int(hd[4:6]) - 1


def season_of(month):
    if month in WINTER:
        return "W"
    if month in SUMMER:
        return "S"
    return ""


def c1_bin(rate):
    if rate is None:
        return "new"
    if rate < 0.15:
        return "lt15"
    if rate < 0.25:
        return "15to25"
    if rate < 0.35:
        return "25to35"
    return "ge35"


def out_bin(rates):
    v = [r for r in rates if r is not None]
    if len(v) < 3:
        return "na"
    m = sum(v) / len(v)
    if m < 0.12:
        return "lt12"
    if m < 0.15:
        return "12to15"
    if m < 0.18:
        return "15to18"
    return "ge18"


def wind_bin(v):
    if v <= 1:
        return "0to1"
    if v <= 3:
        return "2to3"
    if v <= 5:
        return "4to5"
    return "ge6"


def temp_bin(v):
    lo = int(math.floor(v / 5.0)) * 5
    lo = max(min(lo, 30), 0)
    return "%dto%d" % (lo, lo + 5) if lo < 30 else "ge30"


class Racer(object):
    __slots__ = ("m",)

    def __init__(self):
        self.m = {}

    def add(self, mi, win):
        c = self.m.get(mi)
        if c is None:
            c = [0, 0]
            self.m[mi] = c
        c[0] += 1
        if win:
            c[1] += 1

    def prior_rate(self, mi):
        s = 0
        w = 0
        for k in range(mi - 12, mi):
            c = self.m.get(k)
            if c:
                s += c[0]
                w += c[1]
        if s < MIN_STARTS:
            return None
        return float(w) / s

    def trim(self, mi):
        for k in [k for k in self.m if k < mi - 13]:
            del self.m[k]


def cmh_diff(cells):
    """cells: [(n_w, k_w, n_s, k_s)] → 重み付き差（冬−夏）とその重み合計。"""
    num = 0.0
    den = 0.0
    for nw, kw, ns, ks in cells:
        if nw == 0 or ns == 0:
            continue
        wgt = float(nw * ns) / (nw + ns)
        num += wgt * (float(kw) / nw - float(ks) / ns)
        den += wgt
    return (num / den if den else None), den


def null_draws(key, nw, ns, k):
    import numpy as np
    seed = splitmix64(fnv1a64(key) ^ SEED)
    rng = np.random.default_rng(seed)
    x = rng.hypergeometric(k, nw + ns - k, nw, size=NPERM)
    wgt = float(nw * ns) / (nw + ns)
    return wgt * (x / float(nw) - (k - x) / float(ns))


def run_analyze():
    try:
        import numpy as np
    except ImportError:
        stop("numpy が無い")
    parts = [os.path.join(PARTS_DIR, "s1r%s.csv" % y) for y in YEARS]
    miss = [p for p in parts if not os.path.exists(p)]
    if miss:
        stop("rows の中間ファイルが無い: %s" % ", ".join(os.path.basename(p) for p in miss))
    tpath = os.path.join(PARTS_DIR, "s1temps.csv")
    if not os.path.exists(tpath):
        stop("temps の中間ファイルが無い")

    temps = {}
    with io.open(tpath, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            temps[(r["hd"], r["jcd"], int(r["rno"]))] = (float(r["air"]), float(r["water"]))

    racers = {}
    strata = {}                         # key → [nW, kW, nS, kS]
    kim_strata = defaultdict(lambda: {"W": Counter(), "S": Counter(), "nW": 0, "nS": 0})
    raw = {"W": [0, 0], "S": [0, 0]}
    raw_kim = {"W": Counter(), "S": Counter()}
    pairs = defaultdict(lambda: [0, 0, 0, 0])
    solo = defaultdict(lambda: [0, 0, 0, 0])
    wind = defaultdict(lambda: [0, 0])  # (season, windbin) → [n, c1win]
    wind_share = {"W": [0, 0], "S": [0, 0]}
    jcd_rt = defaultdict(lambda: [0.0, 0, 0.0, 0])   # jcd → [sumW, nW, sumS, nS]
    jcd_st = defaultdict(lambda: [0.0, 0, 0.0, 0])
    tcell = defaultdict(lambda: [0, 0])  # ("air"/"water"/"both", bin...) → [n, c1win]
    tstrata = defaultdict(lambda: [0, 0])  # (jcd, c1bin, airbin) → [n, c1win]
    bins_seen = Counter()
    total = 0
    last_mi = None

    for y in YEARS:
        with io.open(os.path.join(PARTS_DIR, "s1r%s.csv" % y), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                total += 1
                hd = r["hd"]
                mi = month_index(hd)
                month = int(hd[4:6])
                if last_mi is not None and mi != last_mi and mi % 6 == 0:
                    for rc in racers.values():
                        rc.trim(mi)
                last_mi = mi
                tob = [r["t%d" % c] for c in range(1, 7)]
                rates = []
                for t in tob:
                    rc = racers.get(t) if t else None
                    rates.append(rc.prior_rate(mi) if rc else None)
                cb = c1_bin(rates[0])
                ob = out_bin(rates[1:])
                win1 = 1 if r["winCourse"] == "1" else 0
                season = season_of(month)
                sy = int(hd[:4]) + (1 if month == 12 else 0)
                jcd = r["jcd"]
                bins_seen[(cb, ob)] += 1

                if season:
                    key = "%s|%d|%s|%s|%s" % (jcd, sy, r["rclass"], cb, ob)
                    c = strata.get(key)
                    if c is None:
                        c = [0, 0, 0, 0]
                        strata[key] = c
                    if season == "W":
                        c[0] += 1
                        c[1] += win1
                    else:
                        c[2] += 1
                        c[3] += win1
                    raw[season][0] += 1
                    raw[season][1] += win1
                    raw_kim[season][r["kim"]] += 1
                    ks = kim_strata[key]
                    ks[season][r["kim"]] += 1
                    ks["n" + season] += 1
                    for p in (pairs[(tob[0], jcd)], solo[tob[0]]):
                        if season == "W":
                            p[0] += 1
                            p[1] += win1
                        else:
                            p[2] += 1
                            p[3] += win1
                    wv = int(r["windMps"])
                    wb = wind_bin(wv)
                    wind[(season, wb)][0] += 1
                    wind[(season, wb)][1] += win1
                    wind_share[season][0] += 1
                    wind_share[season][1] += 1 if wv >= 6 else 0
                    if r["winRt"]:
                        jr = jcd_rt[jcd]
                        if season == "W":
                            jr[0] += float(r["winRt"])
                            jr[1] += 1
                        else:
                            jr[2] += float(r["winRt"])
                            jr[3] += 1
                    if r["c1st"]:
                        js = jcd_st[jcd]
                        if season == "W":
                            js[0] += float(r["c1st"])
                            js[1] += 1
                        else:
                            js[2] += float(r["c1st"])
                            js[3] += 1

                tk = (hd, jcd, int(r["rno"]))
                if tk in temps:
                    a, wt = temps[tk]
                    ab = temp_bin(a)
                    wbn = temp_bin(wt)
                    for cell in (("air", ab), ("water", wbn), ("both", ab, wbn)):
                        tcell[cell][0] += 1
                        tcell[cell][1] += win1
                    ts = tstrata[(jcd, cb, ab)]
                    ts[0] += 1
                    ts[1] += win1

                for pos, t in enumerate(tob):
                    if not t:
                        continue
                    rc = racers.get(t)
                    if rc is None:
                        rc = Racer()
                        racers[t] = rc
                    rc.add(mi, 1 if (pos + 1) == int(r["winCourse"]) else 0)
        print("  analyze %s done races=%d racers=%d" % (y, total, len(racers)))
        sys.stdout.flush()

    if not (520000 <= total <= 570000):
        stop("レース総数が想定外: %d" % total)

    # ---- 主検定：層内の置換 ----
    keys = sorted(k for k, c in strata.items() if c[0] > 0 and c[2] > 0)
    cells = [tuple(strata[k]) for k in keys]
    d_obs, wsum = cmh_diff(cells)
    null = np.zeros(NPERM)
    for k in keys:
        nw, kw, ns, ks = strata[k]
        null += null_draws(k, nw, ns, kw + ks)
    null = null / wsum
    # 分割不変の自己照合：層を2つに分けて足しても同じになる
    half = len(keys) // 2
    n1 = np.zeros(NPERM)
    n2 = np.zeros(NPERM)
    for k in keys[:half]:
        nw, kw, ns, ks = strata[k]
        n1 += null_draws(k, nw, ns, kw + ks)
    for k in keys[half:]:
        nw, kw, ns, ks = strata[k]
        n2 += null_draws(k, nw, ns, kw + ks)
    part_ok = bool(np.allclose((n1 + n2) / wsum, null, rtol=0.0, atol=1e-12))
    p_two = (1.0 + float(np.sum(np.abs(null) >= abs(d_obs)))) / (NPERM + 1.0)
    null_sd = float(np.std(null))

    # ---- 季節年ごとの再現 ----
    by_year = {}
    for sy in range(2017, 2027):
        sub = [tuple(strata[k]) for k in keys if k.split("|")[1] == str(sy)]
        d, w = cmh_diff(sub)
        nW = sum(c[0] for c in sub)
        nS = sum(c[2] for c in sub)
        by_year[str(sy)] = {"diffPt": round(100 * d, 3) if d is not None else None,
                            "nWinter": nW, "nSummer": nS}
    same_sign = sum(1 for v in by_year.values()
                    if v["diffPt"] is not None and d_obs is not None
                    and (v["diffPt"] > 0) == (d_obs > 0) and v["diffPt"] != 0)

    # ---- 決まり手6分類：素の構成比と、層で揃えた差 ----
    kim_out = {}
    for kk in ["nige", "sashi", "makuri", "makurizashi", "nuki", "megumare"]:
        cells_k = []
        for key in keys:
            ks = kim_strata[key]
            cells_k.append((ks["nW"], ks["W"][kk], ks["nS"], ks["S"][kk]))
        d, _ = cmh_diff(cells_k)
        kim_out[kk] = {
            "rawWinterPct": round(100.0 * raw_kim["W"][kk] / raw["W"][0], 3),
            "rawSummerPct": round(100.0 * raw_kim["S"][kk] / raw["S"][0], 3),
            "controlledDiffPt": round(100 * d, 3) if d is not None else None}

    # ---- 個体内：同じ選手 x 同じ場 x 1コースで冬と夏 ----
    pos = 0
    neg = 0
    zero = 0
    num = 0.0
    den = 0.0
    npair = 0
    for (t, j), (nw, kw, ns, ks) in pairs.items():
        if nw < PAIR_MIN or ns < PAIR_MIN:
            continue
        npair += 1
        dd = float(kw) / nw - float(ks) / ns
        if dd > 0:
            pos += 1
        elif dd < 0:
            neg += 1
        else:
            zero += 1
        wgt = float(nw * ns) / (nw + ns)
        num += wgt * dd
        den += wgt
    within = {"pairs": npair, "minEachSeason": PAIR_MIN, "winterHigher": pos,
              "summerHigher": neg, "tie": zero,
              "weightedDiffPt": round(100 * num / den, 3) if den else None}
    spos = 0
    sneg = 0
    snum = 0.0
    sden = 0.0
    sn = 0
    for t, (nw, kw, ns, ks) in solo.items():
        if nw < SOLO_MIN or ns < SOLO_MIN:
            continue
        sn += 1
        dd = float(kw) / nw - float(ks) / ns
        if dd > 0:
            spos += 1
        elif dd < 0:
            sneg += 1
        wgt = float(nw * ns) / (nw + ns)
        snum += wgt * dd
        sden += wgt
    within_solo = {"racers": sn, "minEachSeason": SOLO_MIN, "winterHigher": spos,
                   "summerHigher": sneg,
                   "weightedDiffPt": round(100 * snum / sden, 3) if sden else None}

    # ---- 風 ----
    wind_out = {}
    for s in ("W", "S"):
        for wb in ("0to1", "2to3", "4to5", "ge6"):
            n, k = wind[(s, wb)]
            wind_out["%s_%s" % (s, wb)] = {"n": n, "c1WinPct": round(100.0 * k / n, 2) if n >= CELL_MIN else None}
    wind_ge6 = dict((s, {"n": wind_share[s][0],
                         "ge6Pct": round(100.0 * wind_share[s][1] / wind_share[s][0], 3)})
                    for s in ("W", "S"))

    # ---- 物：1着レースタイムと1コースST（場ごとに揃えて冬−夏）----
    def jcd_mean_diff(src):
        num = 0.0
        den = 0.0
        for j, (sw, nw, ss, ns) in src.items():
            if nw < CELL_MIN or ns < CELL_MIN:
                continue
            wgt = float(nw * ns) / (nw + ns)
            num += wgt * (sw / nw - ss / ns)
            den += wgt
        return round(num / den, 4) if den else None

    # ---- 気温・水温（14か月）----
    tout = {}
    for cell, (n, k) in sorted(tcell.items()):
        tout["|".join(cell)] = {"n": n, "c1WinPct": round(100.0 * k / n, 2) if n >= CELL_MIN else None}
    # 場と1コース選手の強さで揃えた、気温刻みごとの1コース1着率（直接標準化）
    std_w = defaultdict(int)
    for (j, cb, ab), (n, k) in tstrata.items():
        std_w[(j, cb)] += n
    air_std = {}
    for ab in sorted(set(k[2] for k in tstrata)):
        num = 0.0
        den = 0.0
        ncell = 0
        for (j, cb), w in std_w.items():
            n, k = tstrata.get((j, cb, ab), (0, 0))
            if n == 0:
                continue
            num += w * (float(k) / n)
            den += w
            ncell += n
        air_std[ab] = {"n": ncell, "stdC1WinPct": round(100 * num / den, 2) if den and ncell >= CELL_MIN else None}

    summary = {
        "stage": 1,
        "seed": SEED, "nperm": NPERM,
        "races": total,
        "strataUsed": len(keys),
        "rawC1WinPct": {"winter": round(100.0 * raw["W"][1] / raw["W"][0], 3), "nWinter": raw["W"][0],
                        "summer": round(100.0 * raw["S"][1] / raw["S"][0], 3), "nSummer": raw["S"][0]},
        "main": {"controlledDiffPt": round(100 * d_obs, 3), "pTwoSided": round(p_two, 6),
                 "nullSdPt": round(100 * null_sd, 3), "mdePt": round(100 * 2.8 * null_sd, 3),
                 "partitionInvariant": part_ok},
        "byYear": by_year, "yearsSameSign": same_sign,
        "withinRacer": within,
        "withinRacerAllVenues": within_solo,
        "kimarite": kim_out,
        "wind": {"byBin": wind_out, "ge6Share": wind_ge6},
        "things": {"winRaceTimeSecWinterMinusSummer": jcd_mean_diff(jcd_rt),
                   "c1StWinterMinusSummer": jcd_mean_diff(jcd_st)},
        "temps14m": {"cells": tout, "airStandardized": air_std},
        "strengthBins": dict(("%s|%s" % k, v) for k, v in sorted(bins_seen.items())),
        "notes": ["grade not in Kfiles; controlled by prior 12-month win rate instead",
                  "season: winter=Dec,Jan,Feb / summer=Jul,Aug; December counted in next season-year",
                  "cells under %d are not reported as rates" % CELL_MIN],
    }
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "stage1.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"summary": summary}, f, ensure_ascii=False, indent=1)
    print("OK analyze races=%d strata=%d diffPt=%.3f p=%.4f partitionInvariant=%s"
          % (total, len(keys), 100 * d_obs, p_two, part_ok))


def main():
    if len(sys.argv) < 2:
        stop("mode が無い（rows YYYY / temps / analyze）")
    mode = sys.argv[1]
    if mode == "rows":
        if len(sys.argv) < 3:
            stop("rows の年が無い")
        for y in sys.argv[2:]:
            run_rows(y)
    elif mode == "temps":
        run_temps()
    elif mode == "analyze":
        run_analyze()
    else:
        stop("不明な mode: %s" % mode)


if __name__ == "__main__":
    main()
