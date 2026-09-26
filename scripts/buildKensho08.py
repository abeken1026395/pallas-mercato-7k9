# -*- coding: utf-8 -*-
# buildKensho08.py
# 検証08「4カドに実力者がいると荒れる」は本当か -- stage0 から stage2。
#
# 使い方（この順）
#   py scripts\buildKensho08.py rows 2016   （2016 から 2026 まで1年ずつ）
#   py scripts\buildKensho08.py analyze
#   py scripts\buildKensho08.py names 2016   （2016 から 2026 まで1年ずつ）
#   py scripts\buildKensho08.py extra      （stage6。rows と names の後）
#   py scripts\buildKensho08.py pays 2016    （2016 から 2026 まで1年ずつ）
#   py scripts\buildKensho08.py bets       （stage7。rows・names・pays の後）
#   py scripts\buildKensho08.py bprog 2016   （2016 から 2026 まで1年ずつ。番組表の勝率とモーター2連率）
#   py scripts\buildKensho08.py more       （stage8。bprog の後）
#
# rows    : Kファイルを1レースずつ流し、1レース1行のCSVを PARTS_DIR に年ごとに書く（リポジトリの外）
# analyze : 年の順に読み、Bファイル由来の級別の履歴（rankHistory.json）で当日の級別を当て、
#           analysis/kensho08/stage0.json から stage5.json を書く（stage3 は場ごと、stage4 は場を分けるものと水面の条件、stage5 はスタートの前後の分解）
#
# 期間：2016-11-01 から 2026-08-11（Bファイルの在庫の終わり）
# 主な比較：4コースの舟がA1か否かで、1コースの1着率の重み付き差（A1あり − なし）
# 層：場 x 年 x 1コースの選手の級別
# 検定：層の中でラベルを入れ替える置換（超幾何で厳密に同値）。1,000回。
#       層ごとに splitmix64 で種を作り、層の分け方で結果が変わらないことを自己照合する。
import os
import re
import sys
import csv
import glob
import json
import bisect
import shutil
import tempfile
import subprocess
from collections import defaultdict

KFILES_DIR = os.environ.get("K8_KFILES", r"C:\Users\USER\boatrace\data\kfiles")
PARTS_DIR = os.environ.get("K8_PARTS", r"C:\Users\USER\kensho08parts")
RANK_JSON = os.environ.get("K8_RANK", r"C:\Users\USER\bfiles\rankHistory.json")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.environ.get("K8_OUT", os.path.join(ROOT, "analysis", "kensho08"))
K_FROM = "20161101"
K_TO = "20260811"
YEARS = [str(y) for y in range(2016, 2027)]
SEED = 20260925
NPERM = 1000
BSDTAR = shutil.which("bsdtar") or shutil.which("tar") or "tar"
M64 = (1 << 64) - 1

GATE_DAYS = 3571
GATE_RACES = 538268

KIM6 = ["\u9003\u3052", "\u5dee\u3057", "\u307e\u304f\u308a",
        "\u307e\u304f\u308a\u5dee\u3057", "\u629c\u304d", "\u6075\u307e\u308c"]
KIMKEY = {k: i for i, k in enumerate(KIM6)}
CLS = {"A1": 0, "A2": 1, "B1": 2, "B2": 3}

HEAD_RE = re.compile(
    "^\\s+([0-9]+)R[\\s\u3000]+(.+?)[\\s\u3000]+H([0-9]+)m"
    "[\\s\u3000]+([^\\s\u3000]+)[\\s\u3000]+\u98a8[\\s\u3000]+([^\\s\u3000]+)[\\s\u3000]+([0-9]+)m"
    "[\\s\u3000]+\u6ce2[\\s\u3000]+([0-9]+)cm")
ENT_RE = re.compile("^\\s*([0-9A-Z]{1,2})[\\s\u3000]+([1-6])[\\s\u3000]+([0-9]{4})[\\s\u3000]")
SHIN_RE = re.compile("[0-9]+\\.[0-9]{2}[\\s\u3000]+([1-6])[\\s\u3000]+(\\S+)")
TRI_RE = re.compile("^\\s+\uff13\u9023\u5358[\\s\u3000]+([1-6]-[1-6]-[1-6])[\\s\u3000]+([0-9]+)[\\s\u3000]+\u4eba\u6c17[\\s\u3000]+([0-9]+)")
TOKS_RE = re.compile("[\\s\u3000]+")
ROWCOLS = ["hd", "jcd", "rno", "kim", "pay", "c1", "c2", "c3", "c4", "c5", "c6",
           "w1", "w2", "w3", "w4", "w5", "w6", "winC", "winW",
           "st1", "st2", "st3", "st4", "st5", "st6", "windM", "waveCm"]


def stop(msg):
    print("STOP: " + msg)
    sys.exit(1)


def unlzh(path):
    try:
        import lhafile
    except ImportError:
        pass
    else:
        cls = getattr(lhafile, "LhaFile", None) or getattr(lhafile, "Lhafile")
        arc = cls(path)
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


def file_hd(path):
    m = re.search(r"[kK]([0-9]{2})([0-9]{2})([0-9]{2})", os.path.basename(path))
    return "20{}{}{}".format(m.group(1), m.group(2), m.group(3)) if m else ""


def part_path(name):
    return os.path.join(PARTS_DIR, name)


def run_rows(year):
    os.makedirs(PARTS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(KFILES_DIR, "k*.lzh")) + glob.glob(os.path.join(KFILES_DIR, "K*.lzh")))
    files = sorted(set(files))
    days = 0
    races = 0
    fails = []
    out = open(part_path("rows%s.csv" % year), "w", encoding="utf-8", newline="")
    w = csv.writer(out)
    w.writerow(ROWCOLS)
    for p in files:
        hd = file_hd(p)
        if not hd or hd[:4] != year or hd < K_FROM or hd > K_TO:
            continue
        try:
            text = unlzh(p).decode("cp932", errors="replace")
        except Exception as e:
            fails.append([os.path.basename(p), repr(e)])
            continue
        days += 1
        races += scan_day(text, hd, w)
    out.close()
    st = {"year": year, "days": days, "races": races, "readFail": fails}
    with open(part_path("rows%s.json" % year), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    print("rows %s days=%d races=%d readFail=%d" % (year, days, races, len(fails)))


def scan_day(text, hd, w):
    jcd = None
    cur = None
    n = [0]

    def flush():
        if cur is None or not cur["e"]:
            return
        byc = {}
        byw = {}
        bst = {}
        winc = 0
        winw = 0
        for chaku, waku, toban, shin, st in cur["e"]:
            byw[waku] = toban
            if shin:
                byc[shin] = toban
                bst[shin] = st
            if chaku in ("01", "1"):
                winw = waku
                winc = shin or 0
        row = [hd, jcd, cur["rno"], cur["kim"], cur["pay"]]
        row += [byc.get(c, "") for c in range(1, 7)]
        row += [byw.get(k, "") for k in range(1, 7)]
        row += [winc, winw]
        row += [bst.get(c, "") for c in range(1, 7)]
        row += [cur["wind"], cur["wave"]]
        w.writerow(row)
        n[0] += 1

    for ln in text.split("\n"):
        ln = ln.rstrip("\r")
        m = re.match(r"^([0-9]{2})KBGN", ln)
        if m:
            flush()
            cur = None
            jcd = m.group(1)
            continue
        if re.match(r"^([0-9]{2})KEND", ln):
            flush()
            cur = None
            jcd = None
            continue
        if jcd is None:
            continue
        h = HEAD_RE.match(ln)
        if h:
            flush()
            cur = {"rno": int(h.group(1)), "kim": "", "pay": "", "e": [], "wind": h.group(6), "wave": h.group(7)}
            continue
        if cur is None:
            continue
        if "\u767b\u756a" in ln and "\u9078" in ln:
            cur["kim"] = TOKS_RE.split(ln.strip())[-1]
            continue
        t = TRI_RE.match(ln)
        if t:
            cur["pay"] = t.group(2)
            continue
        e = ENT_RE.match(ln)
        if e:
            m2 = SHIN_RE.search(ln[e.end():])
            cur["e"].append((e.group(1), int(e.group(2)), e.group(3), int(m2.group(1)) if m2 else 0, m2.group(2) if m2 else ""))
    flush()
    return n[0]


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


def load_rank():
    with open(RANK_JSON, encoding="utf-8") as f:
        rh = json.load(f)
    return {tb: ([c[0].replace("-", "") for c in v["changes"]], [c[1] for c in v["changes"]]) for tb, v in rh.items()}


def cls_on(look, tb, hd):
    x = look.get(tb)
    if not x:
        return -1
    i = bisect.bisect_right(x[0], hd) - 1
    if i < 0:
        return -1
    return CLS.get(x[1][i], -1)


def perm_test(tag, y, x, strata):
    """重み付き差（x=1 − x=0）と、層ごとの超幾何の置換 NPERM 回。分割不変を自己照合する。"""
    import numpy as np
    y = np.asarray(y, dtype=np.int64)
    x = np.asarray(x, dtype=np.int64)
    keys, inv = np.unique(np.asarray(strata), return_inverse=True)
    n = np.bincount(inv)
    n1 = np.bincount(inv, weights=x).astype(np.int64)
    k = np.bincount(inv, weights=y).astype(np.int64)
    k1 = np.bincount(inv, weights=y * x).astype(np.int64)
    ok = (n1 > 0) & (n1 < n)
    idx = np.where(ok)[0]
    n0 = n - n1
    wgt = n1 * n0 / n.astype(float)
    wsum = float(wgt[idx].sum())
    obs = float((wgt[idx] * (k1[idx] / n1[idx] - (k[idx] - k1[idx]) / n0[idx])).sum() / wsum)
    part = [np.zeros(NPERM), np.zeros(NPERM)]
    for i in idx:
        key = "%s|%s" % (tag, keys[i])
        rng = np.random.default_rng(splitmix64(fnv1a64(key) ^ SEED))
        d = rng.hypergeometric(int(k[i]), int(n[i] - k[i]), int(n1[i]), size=NPERM)
        v = wgt[i] * (d / float(n1[i]) - (k[i] - d) / float(n0[i]))
        part[fnv1a64(key) & 1] += v
    null = (part[0] + part[1]) / wsum
    null2 = np.zeros(NPERM)
    for i in idx[::-1]:
        key = "%s|%s" % (tag, keys[i])
        rng = np.random.default_rng(splitmix64(fnv1a64(key) ^ SEED))
        d = rng.hypergeometric(int(k[i]), int(n[i] - k[i]), int(n1[i]), size=NPERM)
        null2 += wgt[i] * (d / float(n1[i]) - (k[i] - d) / float(n0[i]))
    split_ok = bool(np.allclose(null, null2 / wsum, rtol=0.0, atol=1e-12))
    if not split_ok:
        stop("分割不変の自己照合に失敗: " + tag)
    sd = float(null.std())
    mde = 2.8 * sd
    p = float((np.sum(np.abs(null) >= abs(obs)) + 1) / (NPERM + 1))
    return {"diffPt": round(100 * obs, 4), "p": round(p, 4), "nullSdPt": round(100 * sd, 4),
            "mdePt": round(100 * mde, 4), "fill": round(abs(obs) / mde, 3) if mde > 0 else None,
            "n1": int(n1[idx].sum()), "n0": int(n0[idx].sum()), "strata": int(len(idx)),
            "dropped": int(n[~ok].sum()), "splitOk": split_ok, "_null": null}


def st100(x):
    """スタートタイミングを 1/100 秒の整数に。F・L・欠場など数字でないものは -999。"""
    if x and x[0] in "0.":
        try:
            return int(round(float(x) * 100))
        except ValueError:
            return -999
    return -999


def pub(r):
    return {k: v for k, v in r.items() if not k.startswith("_")}


def run_analyze():
    import numpy as np
    look = load_rank()
    rows = []
    st0 = {"years": {}, "drop": {"kim": 0, "noC1C4": 0, "noClass": 0}}
    days = 0
    fails = []
    for y in YEARS:
        jp = part_path("rows%s.json" % y)
        cp = part_path("rows%s.csv" % y)
        if not (os.path.exists(jp) and os.path.exists(cp)):
            stop("rows %s が無い" % y)
        with open(jp, encoding="utf-8") as f:
            meta = json.load(f)
        days += meta["days"]
        fails += meta["readFail"]
        st0["years"][y] = {"days": meta["days"], "races": meta["races"]}
        with open(cp, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["kim"] not in KIMKEY:
                    st0["drop"]["kim"] += 1
                    continue
                wc = [cls_on(look, r["w%d" % i], r["hd"]) for i in range(1, 7)]
                if min(wc) < 0:
                    st0["drop"]["noClass"] += 1
                    continue
                cc = [cls_on(look, r["c%d" % i], r["hd"]) if r["c%d" % i] else -1 for i in range(1, 7)]
                has14 = int(bool(r["c1"]) and bool(r["c4"]))
                if not has14:
                    st0["drop"]["noC1C4"] += 1
                waknari = int(all(r["c%d" % i] == r["w%d" % i] for i in range(1, 7)))
                w4isC4 = int(bool(r["c4"]) and r["c4"] == r["w4"])
                rows.append([int(r["hd"]), int(r["jcd"]), int(r["winC"] or 0), int(r["winW"] or 0),
                             KIMKEY[r["kim"]], int(r["pay"]) if r["pay"] else -1, has14, waknari, w4isC4,
                             int(r["c1"] or 0)] + cc + wc + [st100(r["st1"]), st100(r["st4"]), int(r["windM"] or -1), int(r["waveCm"] or -1)])
    a = np.array(rows, dtype=np.int64)
    HD, J, WC, WW, KIM, PAY, H14, WN, W4C4, T1 = [a[:, i] for i in range(10)]
    CC = a[:, 10:16]
    WCL = a[:, 16:22]
    YR = HD // 10000
    st0.update({"from": K_FROM, "to": K_TO, "days": days, "readFail": fails,
                "racesAll": int(len(a)), "racesCourse": int(H14.sum())})
    st0["gate"] = {"days": days == GATE_DAYS, "racesCourse": int(H14.sum()) == GATE_RACES, "readFail0": len(fails) == 0}
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "stage0.json"), "w", encoding="utf-8") as f:
        json.dump(st0, f, ensure_ascii=False, indent=1)
    if not all(st0["gate"].values()):
        stop("分母ゲート: " + json.dumps(st0["gate"]))

    # ---- stage1（コース基準） ----
    m = H14 == 1
    c = CC[m]
    y1 = (WC[m] == 1).astype(np.int64)
    y4 = (WC[m] == 4).astype(np.int64)
    x = (c[:, 3] == 0).astype(np.int64)
    j = J[m]
    yr = YR[m]
    pay = PAY[m]
    st = j * 10 ** 6 + yr * 10 + c[:, 0]
    s1 = {}
    s1["raw"] = {"nX": int(x.sum()), "n0": int((1 - x).sum()),
                 "c1WinX": round(100 * float(y1[x == 1].mean()), 4), "c1Win0": round(100 * float(y1[x == 0].mean()), 4),
                 "c1A1shareX": round(100 * float((c[x == 1, 0] == 0).mean()), 4),
                 "c1A1share0": round(100 * float((c[x == 0, 0] == 0).mean()), 4)}
    main = perm_test("main", y1, x, st)
    s1["main"] = pub(main)
    s1["c4win"] = pub(perm_test("c4win", y4, x, st))
    pm = pay >= 0
    s1["manshu"] = pub(perm_test("manshu", (pay[pm] >= 10000).astype(np.int64), x[pm], st[pm]))
    wn = WN[m] == 1
    s1["waknari"] = pub(perm_test("waknari", y1[wn], x[wn], st[wn]))
    s1["waknariN"] = int(wn.sum())
    s1["within"] = pub(perm_test("within", y1, x, T1[m] * 10 + c[:, 0]))
    wk = T1[m] * 10 + c[:, 0]
    both = set(wk[x == 1].tolist()) & set(wk[x == 0].tolist())
    s1["withinGroups"] = int(len(both))
    s1["withinRacers"] = int(len(set(v // 10 for v in both)))
    s1["year"] = {}
    for yy in range(2016, 2027):
        q = yr == yy
        s1["year"][str(yy)] = pub(perm_test("year%d" % yy, y1[q], x[q], (j * 10 + c[:, 0])[q]))
    # 見分けられる最小の差が今回の差まで下がるのに要るレース数と、1場1開催日あたりの件数
    vdays = len(set(zip(HD[m].tolist(), j.tolist())))
    need = int(x.sum()) * (main["mdePt"] / abs(main["diffPt"])) ** 2
    s1["daysToSee"] = {"venueDays": vdays, "a1At4PerVenueDay": round(float(x.sum()) / vdays, 4),
                       "a1At4RacesNeeded": round(need, 1), "venueDaysNeeded": round(need / (float(x.sum()) / vdays), 1)}
    # 枠番基準
    xw = (WCL[:, 3] == 0).astype(np.int64)
    yw1 = (WW == 1).astype(np.int64)
    stw = J * 10 ** 6 + YR * 10 + WCL[:, 0]
    s1["waku"] = {"n": int(len(a)), "nX": int(xw.sum()),
                  "main": pub(perm_test("wmain", yw1, xw, stw)),
                  "w4win": pub(perm_test("w4win", (WW == 4).astype(np.int64), xw, stw)),
                  "w4isC4": round(100 * float(W4C4[m].mean()), 4)}
    pw = PAY >= 0
    s1["waku"]["manshu"] = pub(perm_test("wmanshu", (PAY[pw] >= 10000).astype(np.int64), xw[pw], stw[pw]))
    with open(os.path.join(OUTDIR, "stage1.json"), "w", encoding="utf-8") as f:
        json.dump(s1, f, ensure_ascii=False, indent=1)

    # ---- stage2（セル） ----
    s2 = {"c1Class": {}, "c3Class": {}, "position": {}}
    for ci, nm in enumerate(["A1", "A2", "B1", "B2"]):
        q = c[:, 0] == ci
        r = pub(perm_test("c1_" + nm, y1[q], x[q], st[q]))
        r["n"] = int(q.sum())
        s2["c1Class"][nm] = r
    walls = {}
    for nm, q in [("A", (c[:, 2] == 0) | (c[:, 2] == 1)), ("B", (c[:, 2] == 2) | (c[:, 2] == 3))]:
        walls[nm] = perm_test("c3_" + nm, y1[q], x[q], st[q])
        s2["c3Class"][nm] = pub(walls[nm])
    gap = walls["B"]["diffPt"] - walls["A"]["diffPt"]
    gnull = 100 * (walls["B"]["_null"] - walls["A"]["_null"])
    s2["c3Gap"] = {"gapPt": round(gap, 4), "p": round(float((np.sum(np.abs(gnull) >= abs(gap)) + 1) / (NPERM + 1)), 4),
                   "mdePt": round(2.8 * float(gnull.std()), 4)}
    for k in range(2, 7):
        xk = (c[:, k - 1] == 0).astype(np.int64)
        s2["position"][str(k)] = {"c1Win": pub(perm_test("pos%d" % k, y1, xk, st)),
                                  "manshu": pub(perm_test("posm%d" % k, (pay[pm] >= 10000).astype(np.int64), xk[pm], st[pm]))}
    lose = y1 == 0
    kim = KIM[m]
    wcm = WC[m]
    s2["losers"] = {}
    for nm, q in [("X", x == 1), ("not", x == 0)]:
        ql = lose & q
        mk = ql & (kim == 2)
        s2["losers"][nm] = {"n": int(ql.sum()),
                            "winCourse": {str(v): round(100 * float((wcm[ql] == v).mean()), 4) for v in range(2, 7)},
                            "kim": {KIM6[v]: round(100 * float((kim[ql] == v).mean()), 4) for v in range(6)},
                            "makuriBy4": round(100 * float((wcm[mk] == 4).mean()), 4),
                            "c4WinKim": {KIM6[v]: round(100 * float((kim[ql & (wcm == 4)] == v).mean()), 4) for v in range(6)}}
    s2["c4Winners"] = {}
    for nm, q in [("A1", x == 1), ("notA1", x == 0)]:
        qq = q & (wcm == 4) & pm
        s2["c4Winners"][nm] = {"n": int(qq.sum()), "medianPay": float(np.median(pay[qq])),
                               "manshu": round(100 * float((pay[qq] >= 10000).mean()), 4)}
    with open(os.path.join(OUTDIR, "stage2.json"), "w", encoding="utf-8") as f:
        json.dump(s2, f, ensure_ascii=False, indent=1)
    # ---- stage3（場ごと） ----
    # 場ごとに、年 x 1コースの級別で揃えた差を出す。場の差が偶然を超えるかは、
    # 全場をまとめた差（精度で重み付け）に各場の置換分布を足した 1,000 組の「場の差の標準偏差」と比べる。
    s3 = {"venues": {}}
    ds, ws, nl, bases, mks = [], [], [], [], []
    for v in range(1, 25):
        q = j == v
        r = perm_test("venue%02d" % v, y1[q], x[q], (yr * 10 + c[:, 0])[q])
        rm = perm_test("venueM%02d" % v, (pay[q & pm] >= 10000).astype(np.int64), x[q & pm], (yr * 10 + c[:, 0])[q & pm])
        base = float(y1[q & (x == 0)].mean())
        qx = q & (x == 1)
        mk = float(((wcm[qx] == 4) & (kim[qx] == 2)).mean())
        s3["venues"]["%02d" % v] = {"c1Win": pub(r), "manshu": pub(rm), "n": int(q.sum()),
                                    "c1WinBaseNoA1": round(100 * base, 4), "c4MakuriWinA1": round(100 * mk, 4)}
        ds.append(r["diffPt"]); ws.append(1.0 / (r["nullSdPt"] ** 2)); nl.append(100 * r["_null"]); bases.append(base); mks.append(mk)
    ds = np.array(ds); ws = np.array(ws); nl = np.array(nl)
    pooled = float((ds * ws).sum() / ws.sum())
    sim = (pooled + nl).std(axis=0)
    sdo = float(ds.std())
    s3["spread"] = {"pooledPt": round(pooled, 4), "sdObsPt": round(sdo, 4), "sdNullMeanPt": round(float(sim.mean()), 4),
                    "sdNullMaxPt": round(float(sim.max()), 4), "nullAtLeastObs": int((sim >= sdo).sum()), "nDraws": NPERM,
                    "negativeVenues": int((ds < 0).sum()),
                    "beyondMde": int(sum(1 for v in s3["venues"].values() if abs(v["c1Win"]["diffPt"]) >= v["c1Win"]["mdePt"]))}
    s3["corr"] = {"diffVsBaseNoA1": round(float(np.corrcoef(ds, bases)[0, 1]), 4),
                  "diffVsC4MakuriWinA1": round(float(np.corrcoef(ds, mks)[0, 1]), 4)}
    with open(os.path.join(OUTDIR, "stage3.json"), "w", encoding="utf-8") as f:
        json.dump(s3, f, ensure_ascii=False, indent=1)

    # ---- stage4（場の違いを何が分けるか・水面の条件） ----
    # 場の特徴：A1が4コースにいないレースでの「1コースのST − 4コースのST」の平均（1/100秒）。正なら4コースのほうが早い。
    # 場ごとの差との相関を、場の並びを 10,000 回入れ替えた分布と比べる。風速・波高は場も層に入れて、条件ごとの差を出す。
    ST1 = a[:, 22][m]
    ST4 = a[:, 23][m]
    WDm = a[:, 24][m]
    WVm = a[:, 25][m]
    okst = (ST1 != -999) & (ST4 != -999)
    s4 = {"venues": {}}
    gaps = []
    for v in range(1, 25):
        q = (j == v) & okst & (x == 0)
        gv = float((ST1[q] - ST4[q]).mean())
        gaps.append(gv)
        s4["venues"]["%02d" % v] = {"stGapNoA1": round(gv, 4), "n": int(q.sum())}
    gaps = np.array(gaps)
    r0 = float(np.corrcoef(ds, gaps)[0, 1])
    rng = np.random.default_rng(SEED)
    null = np.array([np.corrcoef(rng.permutation(ds), gaps)[0, 1] for _ in range(10000)])
    slope, icpt = np.polyfit(gaps, ds, 1)
    s4["stGap"] = {"corr": round(r0, 4), "p": round(float((np.sum(np.abs(null) >= abs(r0)) + 1) / 10001), 4),
                   "slopePtPerHundredth": round(float(slope), 4), "gapMin": round(float(gaps.min()), 4), "gapMax": round(float(gaps.max()), 4)}
    stv = j * 10 ** 6 + yr * 10 + c[:, 0]
    s4["wind"] = {}
    s4["wave"] = {}
    keep = {}
    for nm, arr, bins in (("wind", WDm, ((0, 2), (3, 4), (5, 99))), ("wave", WVm, ((0, 2), (3, 5), (6, 999)))):
        for lo, hi in bins:
            q = (arr >= lo) & (arr <= hi)
            rr = perm_test("%s%d" % (nm, lo), y1[q], x[q], stv[q])
            keep[(nm, lo)] = rr
            s4[nm]["%d-%d" % (lo, hi)] = dict(pub(rr), n=int(q.sum()))
        lo_r, hi_r = keep[(nm, bins[0][0])], keep[(nm, bins[-1][0])]
        gap = hi_r["diffPt"] - lo_r["diffPt"]
        gn = 100 * (hi_r["_null"] - lo_r["_null"])
        s4[nm]["gapHighMinusLow"] = {"gapPt": round(gap, 4), "p": round(float((np.sum(np.abs(gn) >= abs(gap)) + 1) / (NPERM + 1)), 4),
                                     "mdePt": round(2.8 * float(gn.std()), 4)}
    with open(os.path.join(OUTDIR, "stage4.json"), "w", encoding="utf-8") as f:
        json.dump(s4, f, ensure_ascii=False, indent=1)
    # ---- stage5（「引いて勝負に出るか」：スタートでつく差と、スタートのあとでつく差・場の差の再現性） ----
    # スタートの遅れ（1コースのST − 4コースのST、1/100秒）を4区分に分け、区分の割合の差（スタート側）と、
    # 同じ区分の中での1着率の差（あと側）に分解する。分解は近似（足した値は全体の差とわずかにずれる）。
    def wd(yv, xv, sv):
        u, inv = np.unique(sv, return_inverse=True)
        nn = np.bincount(inv); m1 = np.bincount(inv, weights=xv)
        sy = np.bincount(inv, weights=yv); sy1 = np.bincount(inv, weights=yv * xv)
        g = (m1 > 0) & (m1 < nn)
        nn, m1, sy, sy1 = nn[g], m1[g], sy[g], sy1[g]
        m0 = nn - m1
        w = m1 * m0 / nn
        return float((w * (sy1 / m1 - (sy - sy1) / m0)).sum() / w.sum())
    SBINS = ((-99, -5), (-4, -1), (0, 4), (5, 99))
    gp = ST1 - ST4
    BIN = np.full(len(gp), -1)
    for bi, (lo, hi) in enumerate(SBINS):
        BIN[okst & (gp >= lo) & (gp <= hi)] = bi
    s5 = {"bins": {}}
    for bi, (lo, hi) in enumerate(SBINS):
        bb = (BIN[okst] == bi).astype(np.int64)
        sh = perm_test("s5share%d" % bi, bb, x[okst], stv[okst])
        q = BIN == bi
        ww = perm_test("s5win%d" % bi, y1[q], x[q], stv[q])
        s5["bins"]["%d..%d" % (lo, hi)] = {"shareDiff": pub(sh), "c1WinDiff": pub(ww), "n": int(q.sum()),
                                           "shareBaseNoA1": round(100 * float(bb[x[okst] == 0].mean()), 4),
                                           "c1WinBaseNoA1": round(100 * float(y1[q & (x == 0)].mean()), 4)}
    s5["a1StartAdvHundredth"] = round(wd(gp[okst].astype(float), x[okst], stv[okst]), 4)

    def decomp(Xv, qv, sv):
        sp = ap = 0.0
        for bi in range(len(SBINS)):
            bb = (BIN[qv] == bi).astype(float)
            q2 = qv & (BIN == bi)
            dsh = wd(bb, Xv[qv], sv[qv])
            dw = wd(y1[q2].astype(float), Xv[q2], sv[q2])
            sp += dsh * float(y1[q2 & (Xv == 0)].mean())
            ap += (float(bb[Xv[qv] == 0].mean()) + dsh) * dw
        return 100 * sp, 100 * ap
    sp0, ap0 = decomp(x, okst, stv)
    s5["decomp"] = {"startPt": round(sp0, 4), "afterPt": round(ap0, 4), "sumPt": round(sp0 + ap0, 4)}
    yc = yr * 10 + c[:, 0]
    dv = np.array([decomp(x, okst & (j == v), yc) for v in range(1, 25)])
    s5["venues"] = {"%02d" % v: {"startPt": round(float(dv[v - 1, 0]), 4), "afterPt": round(float(dv[v - 1, 1]), 4)} for v in range(1, 25)}
    # 場の差が偶然を超えるか：場・年・1コースの級別の組の中で4コースのラベルを入れ替え 200 回、24場の散らばりと比べる
    rng5 = np.random.default_rng(SEED + 5)
    stn = stv[okst]
    o0 = np.argsort(stn, kind="stable")
    xs = x[okst]
    nsd = []
    for _ in range(200):
        o = np.lexsort((rng5.random(len(stn)), stn))
        xp = np.zeros(len(x), dtype=np.int64)
        tmp = np.empty(len(xs), dtype=np.int64)
        tmp[o0] = xs[o]
        xp[okst] = tmp
        nsd.append(np.array([decomp(xp, okst & (j == v), yc) for v in range(1, 25)]).std(axis=0))
    nsd = np.array(nsd)
    osd = dv.std(axis=0)
    s5["venueSpread"] = {"obsSdStart": round(float(osd[0]), 4), "obsSdAfter": round(float(osd[1]), 4),
                         "nullSdStartMean": round(float(nsd[:, 0].mean()), 4), "nullSdStartMax": round(float(nsd[:, 0].max()), 4),
                         "nullSdAfterMean": round(float(nsd[:, 1].mean()), 4), "nullSdAfterMax": round(float(nsd[:, 1].max()), 4),
                         "nullAtLeastStart": int((nsd[:, 0] >= osd[0]).sum()), "nullAtLeastAfter": int((nsd[:, 1] >= osd[1]).sum()), "nDraws": 200}
    # 場の差の再現性：2017-2021 と 2022-2026 に分けて、場ごとの差を出し直す
    h = {}
    for nm, q0 in (("2017-2021", (yr >= 2017) & (yr <= 2021)), ("2022-2026", yr >= 2022)):
        h[nm] = np.array([100 * wd(y1[q0 & (j == v)].astype(float), x[q0 & (j == v)], yc[q0 & (j == v)]) for v in range(1, 25)])
    hk = list(h.keys())
    rk = [np.argsort(np.argsort(h[k])) for k in hk]
    s5["halves"] = {"venues": {"%02d" % v: {k: round(float(h[k][v - 1]), 4) for k in hk} for v in range(1, 25)},
                    "corr": round(float(np.corrcoef(h[hk[0]], h[hk[1]])[0, 1]), 4),
                    "rankCorr": round(float(np.corrcoef(rk[0], rk[1])[0, 1]), 4),
                    "top6": {k: ["%02d" % (i + 1) for i in np.argsort(h[k])[:6]] for k in hk},
                    "bottom6": {k: ["%02d" % (i + 1) for i in np.argsort(h[k])[-6:]] for k in hk}}
    with open(os.path.join(OUTDIR, "stage5.json"), "w", encoding="utf-8") as f:
        json.dump(s5, f, ensure_ascii=False, indent=1)
    print("analyze OK races=%d main=%.4f mde=%.4f" % (int(H14.sum()), s1["main"]["diffPt"], s1["main"]["mdePt"]))


def run_names(year):
    """Kファイルから、レースごとのレース名（予選・準優勝戦など）を names{year}.tsv に書く。"""
    os.makedirs(PARTS_DIR, exist_ok=True)
    files = sorted(set(glob.glob(os.path.join(KFILES_DIR, "k*.lzh")) + glob.glob(os.path.join(KFILES_DIR, "K*.lzh"))))
    n = 0
    with open(part_path("names%s.tsv" % year), "w", encoding="utf-8", newline="") as out:
        for p in files:
            hd = file_hd(p)
            if not hd or hd[:4] != year or hd < K_FROM or hd > K_TO:
                continue
            text = unlzh(p).decode("cp932", errors="replace")
            jcd = None
            for ln in text.split("\n"):
                ln = ln.rstrip("\r")
                m = re.match(r"^([0-9]{2})KBGN", ln)
                if m:
                    jcd = m.group(1)
                    continue
                if re.match(r"^([0-9]{2})KEND", ln):
                    jcd = None
                    continue
                if jcd is None:
                    continue
                h = HEAD_RE.match(ln)
                if h:
                    out.write("%s\t%s\t%d\t%s\n" % (hd, jcd, int(h.group(1)), TOKS_RE.sub("", h.group(2))))
                    n += 1
    print("names %s races=%d" % (year, n))


def race_type(nm):
    # 0 優勝戦 / 1 準優 / 2 選抜・特選・特賞・ドリームなど / 3 予選・一般・その他
    if nm is None:
        return -1
    if "優勝" in nm and "準" not in nm:
        return 0
    if "準優" in nm:
        return 1
    for k in ("ドリーム", "選抜", "特選", "特賞", "特別"):
        if k in nm:
            return 2
    return 3


def run_extra():
    """stage6：揃える条件を増やした確かめ・レースの種類別・基準の率・開催日単位の揺れ・風と波の相互の揃え。"""
    import numpy as np
    look = load_rank()
    names = {}
    for y in YEARS:
        p = part_path("names%s.tsv" % y)
        if not os.path.exists(p):
            stop("names %s が無い" % y)
        with open(p, encoding="utf-8") as f:
            for ln in f:
                d, jj, r, nm = ln.rstrip("\n").split("\t")
                names[(d, int(jj), int(r))] = nm
    rows = []
    for y in YEARS:
        with open(part_path("rows%s.csv" % y), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["kim"] not in KIMKEY or not (r["c1"] and r["c4"]):
                    continue
                wc = [cls_on(look, r["w%d" % i], r["hd"]) for i in range(1, 7)]
                if min(wc) < 0:
                    continue
                cc = [cls_on(look, r["c%d" % i], r["hd"]) if r["c%d" % i] else -1 for i in range(1, 7)]
                nm = names.get((r["hd"], int(r["jcd"]), int(r["rno"])))
                rows.append([int(r["hd"]), int(r["jcd"]), int(r["rno"]), int(r["winC"] or 0),
                             int(r["pay"]) if r["pay"] else -1, int(r["windM"] or -1), int(r["waveCm"] or -1),
                             race_type(nm), int(bool(nm) and "進入固定" in nm)] + cc)
    a = np.array(rows, dtype=np.int64)
    HD, J, RNO, WC, PAY, WD, WV, RT, FIX = [a[:, i] for i in range(9)]
    CC = a[:, 9:15]
    YR = HD // 10000
    if len(a) != GATE_RACES or (RT < 0).any():
        stop("stage6 分母: %d / レース名なし %d" % (len(a), int((RT < 0).sum())))
    y1 = (WC == 1).astype(np.int64)
    x = (CC[:, 3] == 0).astype(np.int64)
    base = J * 10 ** 6 + YR * 10 + CC[:, 0]
    oth = np.minimum((CC[:, 1] == 0).astype(np.int64) + (CC[:, 2] == 0) + (CC[:, 4] == 0) + (CC[:, 5] == 0), 2)
    vd = HD * 100 + J
    u, inv = np.unique(vd, return_inverse=True)
    a1 = np.bincount(inv, weights=(CC == 0).sum(axis=1)) / np.bincount(inv, weights=(CC >= 0).sum(axis=1))
    qs = np.quantile(a1, [0.2, 0.4, 0.6, 0.8])
    MS = np.digitize(a1[inv], qs)
    s6 = {"n": int(len(a)), "raceTypeN": {str(k): int((RT == k).sum()) for k in range(4)}, "fixedN": int(FIX.sum())}
    s6["controls"] = {
        "otherA1": pub(perm_test("x6oth", y1, x, base * 10 + oth)),
        "raceType": pub(perm_test("x6rt", y1, x, base * 10 + RT)),
        "meetA1": pub(perm_test("x6ms", y1, x, base * 10 + MS)),
        "all3": pub(perm_test("x6all", y1, x, (base * 10 + RT) * 100 + MS * 10 + oth)),
        "raceNo": pub(perm_test("x6rno", y1, x, base * 100 + RNO)),
        "noFixed": pub(perm_test("x6fix", y1[FIX == 0], x[FIX == 0], base[FIX == 0])),
        "otherA1None": pub(perm_test("x6none", y1[oth == 0], x[oth == 0], base[oth == 0]))}
    s6["raceType"] = {}
    for k in range(4):
        q = RT == k
        s6["raceType"][str(k)] = dict(pub(perm_test("x6rt%d" % k, y1[q], x[q], base[q])), n=int(q.sum()),
                                      c1WinBaseNoA1=round(100 * float(y1[q & (x == 0)].mean()), 4))
    s6["positionOtherA1"] = {}
    for k in range(2, 7):
        xk = (CC[:, k - 1] == 0).astype(np.int64)
        ok = [i for i in (1, 2, 3, 4, 5) if i != k - 1]
        o = np.minimum(sum((CC[:, i] == 0).astype(np.int64) for i in ok), 2)
        s6["positionOtherA1"][str(k)] = pub(perm_test("x6pos%d" % k, y1, xk, base * 10 + o))
    # 開催日（場 x 日）を単位に引き直したときの、主な差の揺れ
    rng = np.random.default_rng(SEED + 6)
    keys, sinv = np.unique(base, return_inverse=True)
    bs = []
    for _ in range(200):
        wv = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u))[inv].astype(float)
        n = np.bincount(sinv, weights=wv); n1 = np.bincount(sinv, weights=wv * x)
        sy = np.bincount(sinv, weights=wv * y1); sy1 = np.bincount(sinv, weights=wv * y1 * x)
        g = (n1 > 0) & (n1 < n)
        n, n1, sy, sy1 = n[g], n1[g], sy[g], sy1[g]
        n0 = n - n1
        ww = n1 * n0 / n
        bs.append(100 * float((ww * (sy1 / n1 - (sy - sy1) / n0)).sum() / ww.sum()))
    s6["clusterBootSdPt"] = round(float(np.std(bs)), 4)
    # 基準の率
    s6["base"] = {"c1WinNoA1": round(100 * float(y1[x == 0].mean()), 4),
                  "c1WinByClassNoA1": {nm: round(100 * float(y1[(CC[:, 0] == ci) & (x == 0)].mean()), 4) for ci, nm in enumerate(["A1", "A2", "B1", "B2"])},
                  "manshuNoA1": round(100 * float((PAY[(PAY >= 0) & (x == 0)] >= 10000).mean()), 4)}
    # 風と波：もう一方を層に入れて出し直す
    wdb = np.digitize(WD, [3, 5])
    wvb = np.digitize(WV, [3, 6])
    s6["windCtrlWave"] = {}
    s6["waveCtrlWind"] = {}
    for b in range(3):
        q = wdb == b
        s6["windCtrlWave"][str(b)] = pub(perm_test("x6wd%d" % b, y1[q], x[q], (base * 10 + wvb)[q]))
        q = wvb == b
        s6["waveCtrlWind"][str(b)] = pub(perm_test("x6wv%d" % b, y1[q], x[q], (base * 10 + wdb)[q]))
    s6["windWaveCorr"] = round(float(np.corrcoef(WD[(WD >= 0) & (WV >= 0)], WV[(WD >= 0) & (WV >= 0)])[0, 1]), 4)
    s6["venueDaysPerVenuePerYear"] = round(len(u) / 24 / (GATE_DAYS / 365.25), 2)
    # カド受け（3コース）の級別：レースの種類も揃えて出し直す
    st3 = base * 10 + RT
    wl = {}
    for nm, q in (("A", (CC[:, 2] == 0) | (CC[:, 2] == 1)), ("B", (CC[:, 2] == 2) | (CC[:, 2] == 3))):
        wl[nm] = perm_test("x6c3" + nm, y1[q], x[q], st3[q])
    g3 = wl["B"]["diffPt"] - wl["A"]["diffPt"]
    gn3 = 100 * (wl["B"]["_null"] - wl["A"]["_null"])
    s6["c3ClassRaceType"] = {"A": pub(wl["A"]), "B": pub(wl["B"]), "gapPt": round(g3, 4),
                             "gapP": round(float((np.sum(np.abs(gn3) >= abs(g3)) + 1) / (NPERM + 1)), 4),
                             "gapMdePt": round(2.8 * float(gn3.std()), 4)}
    # 4コースがA2のとき（A1のレースを除き、A2かB級かで比べる）
    q = CC[:, 3] != 0
    s6["c4A2vsB"] = pub(perm_test("x6a2", y1[q], (CC[q, 3] == 1).astype(np.int64), base[q]))
    # 払戻の中央値（揃える前）：全レースと、1コースが負けたレース
    pm = PAY >= 0
    s6["payMedian"] = {"allA1": float(np.median(PAY[pm & (x == 1)])), "allNoA1": float(np.median(PAY[pm & (x == 0)])),
                       "c1LoseA1": float(np.median(PAY[pm & (x == 1) & (y1 == 0)])), "c1LoseNoA1": float(np.median(PAY[pm & (x == 0) & (y1 == 0)]))}
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "stage6.json"), "w", encoding="utf-8") as f:
        json.dump(s6, f, ensure_ascii=False, indent=1)
    print("extra OK n=%d all3=%.4f" % (len(a), s6["controls"]["all3"]["diffPt"]))


PAY_LABELS = {"単勝": "tan", "複勝": "fuku", "２連単": "n2t", "３連単": "n3t"}


def run_pays(year):
    """Kファイルから、レースごとの着順（艇番の1から3着）と、単勝・複勝・2連単・3連単の払戻を pays{year}.tsv に書く。"""
    os.makedirs(PARTS_DIR, exist_ok=True)
    files = sorted(set(glob.glob(os.path.join(KFILES_DIR, "k*.lzh")) + glob.glob(os.path.join(KFILES_DIR, "K*.lzh"))))
    n = 0
    with open(part_path("pays%s.tsv" % year), "w", encoding="utf-8", newline="") as out:
        for p in files:
            hd = file_hd(p)
            if not hd or hd[:4] != year or hd < K_FROM or hd > K_TO:
                continue
            text = unlzh(p).decode("cp932", errors="replace")
            jcd = None
            cur = None
            last = None

            def flush():
                if cur is None:
                    return
                order = "".join(str(b) for c, b in sorted(cur["o"]) if c <= 3)
                out.write("%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s\t%s\n" % (hd, jcd, cur["rno"], order, ";".join(cur["tan"]),
                                                                ";".join(cur["fuku"]), ";".join(cur["n2t"]), ";".join(cur["n3t"]),
                                                                ",".join(cur["tj"].get(w, "") for w in range(1, 7))))
            for ln in text.split("\n"):
                ln = ln.rstrip("\r")
                m = re.match(r"^([0-9]{2})KBGN", ln)
                if m:
                    flush(); cur = None
                    jcd = m.group(1)
                    continue
                if re.match(r"^([0-9]{2})KEND", ln):
                    flush(); cur = None
                    jcd = None
                    continue
                if jcd is None:
                    continue
                h = HEAD_RE.match(ln)
                if h:
                    flush()
                    n += 1
                    cur = {"rno": int(h.group(1)), "o": [], "tan": [], "fuku": [], "n2t": [], "n3t": [], "tj": {}}
                    last = None
                    continue
                if cur is None:
                    continue
                e = ENT_RE.match(ln)
                if e:
                    tj = re.search("([0-9]\\.[0-9]{2})[\\s\u3000]+[1-6][\\s\u3000]", ln[e.end():])
                    if tj:
                        cur["tj"][int(e.group(2))] = tj.group(1)
                    if e.group(1).isdigit():
                        cur["o"].append((int(e.group(1)), int(e.group(2))))
                    continue
                t = TOKS_RE.split(ln.strip())
                if not t or not t[0]:
                    continue
                if t[0] in PAY_LABELS:
                    last = PAY_LABELS[t[0]]
                    t = t[1:]
                elif t[0] in ("２連複", "拡連複", "３連複"):
                    last = None
                    continue
                elif last is None or not re.match(r"^[1-6](-[1-6]){0,2}$", t[0]):
                    last = None if not re.match(r"^[1-6](-[1-6]){0,2}$", t[0]) else last
                    continue
                k = 0
                while k + 1 < len(t):
                    if re.match(r"^[1-6](-[1-6]){0,2}$", t[k]) and t[k + 1].isdigit():
                        cur[last].append("%s:%s" % (t[k], t[k + 1]))
                        k += 2
                        if k < len(t) and t[k] == "人気":
                            k += 2
                    else:
                        k += 1
            flush()
    print("pays %s races=%d" % (year, n))


def run_bets():
    """stage7：出走表の枠番で見た舟券の回収率。単勝・複勝・2連単・3連単の払戻と、1号艇の3着内率。開催日を単位に引き直した揺れも付ける。"""
    import numpy as np
    look = load_rank()
    pay = {}
    names = {}
    for y in YEARS:
        for nm, d in (("pays", pay), ("names", names)):
            p = part_path("%s%s.tsv" % (nm, y))
            if not os.path.exists(p):
                stop("%s %s が無い" % (nm, y))
            with open(p, encoding="utf-8") as f:
                for ln in f:
                    v = ln.rstrip("\n").split("\t")
                    d[(v[0], int(v[1]), int(v[2]))] = v[3:8] if nm == "pays" else v[3]

    def amt(s, key):
        return sum(int(x.split(":")[1]) for x in s.split(";") if x and x.split(":")[0] == key)

    def pre(s, head):
        return sum(int(x.split(":")[1]) for x in s.split(";") if x and x.split(":")[0].startswith(head))
    rows = []
    skipped = 0
    for y in YEARS:
        with open(part_path("rows%s.csv" % y), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["kim"] not in KIMKEY:
                    continue
                wc = [cls_on(look, r["w%d" % i], r["hd"]) for i in range(1, 7)]
                if min(wc) < 0:
                    continue
                k = (r["hd"], int(r["jcd"]), int(r["rno"]))
                p = pay.get(k)
                if not p or not p[1]:
                    skipped += 1
                    continue
                o, tan, fu, n2, n3 = p
                rows.append([int(r["hd"]), int(r["jcd"]), race_type(names.get(k)), int(r["windM"] or -1)] + wc +
                            [amt(tan, "1"), amt(tan, "4"), amt(fu, "1"), amt(fu, "4"), amt(n2, "1-4"), amt(n2, "4-1"),
                             pre(n3, "4-"), pre(n3, "1-"), int("1" in o[:3]), int(o[:1] == "4")])
    a = np.array(rows, dtype=np.int64)
    HD, J, RT, WD = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    W = a[:, 4:10]
    vd = HD * 100 + J
    u, inv = np.unique(vd, return_inverse=True)
    rng = np.random.default_rng(SEED + 7)
    BS = [np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u)) for _ in range(200)]
    bets = (("tan1", 10, 100), ("tan4", 11, 100), ("fuku1", 12, 100), ("fuku4", 13, 100), ("n2t14", 14, 100),
            ("n2t41", 15, 100), ("n3t4all", 16, 2000), ("n3t1all", 17, 2000))

    def rr(q, col, cost):
        ii = inv[q]
        v = a[q, col].astype(float)
        sv = np.bincount(ii, weights=v, minlength=len(u))
        sn = np.bincount(ii, minlength=len(u))
        bs = [(sv * b).sum() / (cost * (sn * b).sum()) for b in BS]
        return {"pct": round(100 * float(v.sum()) / (cost * int(q.sum())), 2), "sdPt": round(100 * float(np.std(bs)), 2)}
    X = W[:, 3] == 0
    B1 = W[:, 0] == 2
    WN = WD >= 5
    conds = (("all", np.ones(len(a), bool)), ("w4A1", X), ("w4NotA1", ~X), ("w4A1w1B1", X & B1), ("w4NotA1w1B1", ~X & B1),
             ("w4A1wind5", X & WN), ("w4NotA1wind5", ~X & WN), ("w4A1w1B1wind5", X & B1 & WN), ("w4NotA1w1B1wind5", ~X & B1 & WN),
             ("w4A1wind0_2", X & (WD >= 0) & (WD <= 2)), ("w4A1yosen", X & (RT == 3)))
    s7 = {"n": int(len(a)), "skippedNoTan": skipped, "conds": {}}
    for nm, q in conds:
        s7["conds"][nm] = {"n": int(q.sum()), "boat1In3": round(100 * float(a[q, 18].mean()), 2),
                           "boat4Win": round(100 * float(a[q, 19].mean()), 2)}
        for bn, c, cost in bets:
            s7["conds"][nm][bn] = rr(q, c, cost)
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "stage7.json"), "w", encoding="utf-8") as f:
        json.dump(s7, f, ensure_ascii=False, indent=1)
    print("bets OK n=%d" % len(a))


BFILES_DIR = os.environ.get("K8_BFILES", r"C:\Users\USER\bfiles")
BRACE_RE = re.compile("^[\\s\u3000]*([\uff10-\uff19]+)\uff32")
BBOAT_RE = re.compile("^([1-6]) ([0-9]{4}).*?([AB][12])\\s+([0-9.]+)\\s+([0-9.]+)\\s+([0-9.]+)\\s+([0-9.]+)\\s+([0-9]+)\\s+([0-9.]+)\\s+([0-9]+)\\s+([0-9.]+)")


def run_bprog(year):
    """番組表（Bファイル）から、レースごと・枠ごとの全国勝率とモーター2連率を bprog{year}.tsv に書く。"""
    os.makedirs(PARTS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(BFILES_DIR, year + "[0-9][0-9]", "b*.lzh")))
    n = 0
    with open(part_path("bprog%s.tsv" % year), "w", encoding="utf-8", newline="") as out:
        for p in files:
            m = re.search(r"b([0-9]{6})\.lzh$", os.path.basename(p))
            if not m:
                continue
            hd = "20" + m.group(1)
            if hd < K_FROM or hd > K_TO:
                continue
            text = unlzh(p).decode("cp932", errors="replace")
            jcd = None
            rno = None
            boats = {}

            def flush():
                if jcd and rno and len(boats) == 6:
                    out.write("%s\t%s\t%d\t%s\n" % (hd, jcd, rno, "\t".join("%s:%s:%s" % boats[w] for w in range(1, 7))))
            for ln in text.split("\n"):
                ln = ln.rstrip("\r")
                mm = re.match(r"^([0-9]{2})BBGN", ln)
                if mm:
                    flush(); boats = {}; rno = None
                    jcd = mm.group(1)
                    continue
                if re.match(r"^([0-9]{2})BEND", ln):
                    flush(); boats = {}; rno = None; jcd = None
                    continue
                if jcd is None:
                    continue
                r = BRACE_RE.match(ln)
                if r and "\uff28" in ln:
                    flush(); boats = {}
                    rno = int(r.group(1).translate(str.maketrans("\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19", "0123456789")))
                    n += 1
                    continue
                b = BBOAT_RE.match(ln)
                if b and rno:
                    boats[int(b.group(1))] = (b.group(2), b.group(4), b.group(9))
            flush()
    print("bprog %s races=%d" % (year, n))


def run_more():
    """stage8：1着の行き先・級別と勝率の段差・4コースA1の勝率・モーター2連率・展示タイム順位・回収率の揃え直し。"""
    import numpy as np
    look = load_rank()
    P, BP, NM = {}, {}, {}
    for y in YEARS:
        for nm in ("pays", "bprog", "names"):
            p = part_path("%s%s.tsv" % (nm, y))
            if not os.path.exists(p):
                stop("%s %s が無い" % (nm, y))
            with open(p, encoding="utf-8") as f:
                for ln in f:
                    v = ln.rstrip("\n").split("\t")
                    k = (v[0], int(v[1]), int(v[2]))
                    if nm == "pays":
                        P[k] = v[3:]
                    elif nm == "bprog":
                        BP[k] = {x.split(":")[0]: (float(x.split(":")[1]), float(x.split(":")[2])) for x in v[3:9]}
                    else:
                        NM[k] = v[3]

    def amt(s, key):
        return sum(int(x.split(":")[1]) for x in s.split(";") if x and x.split(":")[0] == key)
    rows = []
    for y in YEARS:
        with open(part_path("rows%s.csv" % y), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["kim"] not in KIMKEY or not (r["c1"] and r["c4"]):
                    continue
                wc = [cls_on(look, r["w%d" % i], r["hd"]) for i in range(1, 7)]
                if min(wc) < 0:
                    continue
                cc = [cls_on(look, r["c%d" % i], r["hd"]) if r["c%d" % i] else -1 for i in range(1, 7)]
                k = (r["hd"], int(r["jcd"]), int(r["rno"]))
                p = P.get(k)
                bp = BP.get(k, {})
                tan = fu = ""
                tj = [""] * 6
                if p:
                    tan, fu = p[1], p[2]
                    tj = p[5].split(",") if len(p) > 5 else tj

                def crs(c):
                    t = r["c%d" % c]
                    w = [i for i in range(1, 7) if r["w%d" % i] == t]
                    w = w[0] if w else 0
                    g, m = bp.get(t, (-1, -1))
                    tt = float(tj[w - 1]) if w and tj[w - 1] else -1
                    return g, m, tt
                c1, c4 = crs(1), crs(4)
                tja = [float(v) for v in tj if v]
                rk4 = sum(1 for v in tja if v < c4[2]) if c4[2] > 0 and len(tja) == 6 else -1
                rows.append([int(r["hd"]), int(r["jcd"]), int(r["winC"] or 0), int(r["windM"] or -1)] + cc + wc +
                            [int(round(c1[0] * 100)), int(round(c1[1] * 100)), int(round(c4[0] * 100)), int(round(c4[1] * 100)), rk4,
                             int(bool(p and tan))] + [amt(tan, str(i)) for i in range(1, 7)] + [amt(fu, str(i)) for i in range(1, 7)])
    a = np.array(rows, dtype=np.int64)
    if len(a) != GATE_RACES:
        stop("stage8 分母: %d" % len(a))
    HD, J, WC, WD = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    CC = a[:, 4:10]
    W = a[:, 10:16]
    C1G, C1M, C4G, C4M, TJ4, HP = [a[:, i] for i in range(16, 22)]
    TAN = a[:, 22:28]
    FU = a[:, 28:34]
    YR = HD // 10000
    x = (CC[:, 3] == 0).astype(np.int64)
    y1 = (WC == 1).astype(np.int64)
    base = J * 10 ** 6 + YR * 10 + CC[:, 0]
    s8 = {"n": int(len(a))}
    s8["winShift"] = {str(c): pub(perm_test("x8ws%d" % c, (WC == c).astype(np.int64), x, base)) for c in range(1, 7)}
    s8["classGrid"] = {nm: {nm2: {"c1Win": round(100 * float(y1[(CC[:, 0] == i) & (CC[:, 3] == j)].mean()), 4),
                                  "n": int(((CC[:, 0] == i) & (CC[:, 3] == j)).sum())} for j, nm2 in enumerate(["A1", "A2", "B1", "B2"])}
                       for i, nm in enumerate(["A1", "A2", "B1", "B2"])}
    okg = (C1G > 0) & (C4G > 0)
    d = (C4G - C1G) / 100.0
    s8["rateGap"] = {}
    for lo, hi in ((-9, -2), (-2, -1), (-1, 0), (0, 1), (1, 2), (2, 9)):
        q = okg & (d >= lo) & (d < hi)
        s8["rateGap"]["%d..%d" % (lo, hi)] = {"n": int(q.sum()), "c1Win": round(100 * float(y1[q].mean()), 4),
                                              "c4Win": round(100 * float((WC[q] == 4).mean()), 4)}
    qa = okg & (x == 1)
    t1, t2 = np.quantile(C4G[qa], [1 / 3.0, 2 / 3.0])
    s8["a1RateTertile"] = {"cutRate": [round(float(t1) / 100, 2), round(float(t2) / 100, 2)]}
    for nm, lo, hi in (("low", 0, t1), ("mid", t1, t2), ("high", t2, 10 ** 6)):
        q = okg & ((x == 0) | ((C4G >= lo) & (C4G < hi)))
        s8["a1RateTertile"][nm] = pub(perm_test("x8rt" + nm, y1[q], x[q], base[q]))
    okm = (C1M > 0) & (C4M > 0)
    dm = (C4M - C1M) / 100.0
    s8["motorGap"] = {}
    for lo, hi in ((-99, -10), (-10, 0), (0, 10), (10, 99)):
        q = okm & (dm >= lo) & (dm < hi)
        s8["motorGap"]["%d..%d" % (lo, hi)] = dict(pub(perm_test("x8mg%d" % lo, y1[q], x[q], base[q])), n=int(q.sum()),
                                                   c1WinNoA1=round(100 * float(y1[q & (x == 0)].mean()), 4))
    okt = TJ4 >= 0
    s8["tenjiRank4"] = {}
    for nm, lo, hi in (("1-2", 0, 1), ("3-4", 2, 3), ("5-6", 4, 5)):
        q = okt & (TJ4 >= lo) & (TJ4 <= hi)
        s8["tenjiRank4"][nm] = dict(pub(perm_test("x8tj" + nm, y1[q], x[q], base[q])), n=int(q.sum()),
                                    c1WinA1=round(100 * float(y1[q & (x == 1)].mean()), 4), c1WinNoA1=round(100 * float(y1[q & (x == 0)].mean()), 4))
    # 回収率を、場・年・1号艇の級別で揃えて比べる（枠番）。開催日を単位に引き直した揺れつき
    hp = HP == 1
    xw = (W[:, 3] == 0).astype(float)
    sw = J * 10 ** 6 + YR * 10 + W[:, 0]
    vd = HD * 100 + J
    u, inv = np.unique(vd, return_inverse=True)
    rng = np.random.default_rng(SEED + 8)
    BS = [np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u)) for _ in range(100)]

    def wdw(yv, xv, sv, wt):
        uu, ii = np.unique(sv, return_inverse=True)
        nn = np.bincount(ii, weights=wt); m1 = np.bincount(ii, weights=wt * xv)
        sy = np.bincount(ii, weights=wt * yv); sy1 = np.bincount(ii, weights=wt * yv * xv)
        g = (m1 > 0) & (m1 < nn)
        nn, m1, sy, sy1 = nn[g], m1[g], sy[g], sy1[g]
        m0 = nn - m1
        w = m1 * m0 / nn
        return float((w * (sy1 / m1 - (sy - sy1) / m0)).sum() / w.sum())

    def adj(yv, xv, q):
        o = wdw(yv[q], xv[q], sw[q], np.ones(int(q.sum())))
        bs = [wdw(yv[q], xv[q], sw[q], b[inv[q]].astype(float)) for b in BS]
        return {"diffPt": round(o, 2), "sdPt": round(float(np.std(bs)), 2), "bs": bs}
    s8["returnAdj"] = {}
    for nm, col in (("tan1", TAN[:, 0]), ("tan4", TAN[:, 3]), ("fuku1", FU[:, 0]), ("fuku4", FU[:, 3])):
        yv = col.astype(float)
        r = adj(yv, xw, hp)
        s8["returnAdj"][nm] = {"diffPt": r["diffPt"], "sdPt": r["sdPt"]}
        w5 = adj(yv, xw, hp & (WD >= 5))
        w0 = adj(yv, xw, hp & (WD >= 0) & (WD <= 2))
        did = np.array(w5["bs"]) - np.array(w0["bs"])
        s8["returnAdj"][nm + "Wind"] = {"wind5": w5["diffPt"], "wind0_2": w0["diffPt"], "didPt": round(w5["diffPt"] - w0["diffPt"], 2),
                                        "didSdPt": round(float(did.std()), 2)}
    x6 = (W[:, 5] == 0).astype(float)
    s8["boat6A1"] = {}
    for nm, col in (("tan6", TAN[:, 5]), ("fuku6", FU[:, 5])):
        yv = col.astype(float)
        s8["boat6A1"][nm] = {"pctA1": round(float(yv[hp & (x6 == 1)].mean()), 2), "pctNoA1": round(float(yv[hp & (x6 == 0)].mean()), 2),
                             "nA1": int((hp & (x6 == 1)).sum())}
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "stage8.json"), "w", encoding="utf-8") as f:
        json.dump(s8, f, ensure_ascii=False, indent=1)
    print("more OK n=%d" % len(a))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "rows":
        if sys.argv[2] not in YEARS:
            stop("年は 2016 から 2026")
        run_rows(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "analyze":
        run_analyze()
    elif len(sys.argv) >= 3 and sys.argv[1] == "names":
        if sys.argv[2] not in YEARS:
            stop("年は 2016 から 2026")
        run_names(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "extra":
        run_extra()
    elif len(sys.argv) >= 3 and sys.argv[1] == "pays":
        if sys.argv[2] not in YEARS:
            stop("年は 2016 から 2026")
        run_pays(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "bets":
        run_bets()
    elif len(sys.argv) >= 3 and sys.argv[1] == "bprog":
        if sys.argv[2] not in YEARS:
            stop("年は 2016 から 2026")
        run_bprog(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "more":
        run_more()
    else:
        stop("使い方：rows YYYY ／ analyze ／ names YYYY ／ extra ／ pays YYYY ／ bets ／ bprog YYYY ／ more")


if __name__ == "__main__":
    main()
