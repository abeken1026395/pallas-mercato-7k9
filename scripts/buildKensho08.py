# -*- coding: utf-8 -*-
# buildKensho08.py
# 検証08「4カドに実力者がいると荒れる」は本当か -- stage0 から stage2。
#
# 使い方（この順）
#   py scripts\buildKensho08.py rows 2016   （2016 から 2026 まで1年ずつ）
#   py scripts\buildKensho08.py analyze
#
# rows    : Kファイルを1レースずつ流し、1レース1行のCSVを PARTS_DIR に年ごとに書く（リポジトリの外）
# analyze : 年の順に読み、Bファイル由来の級別の履歴（rankHistory.json）で当日の級別を当て、
#           analysis/kensho08/stage0.json・stage1.json・stage2.json を書く
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
SHIN_RE = re.compile("[0-9]+\\.[0-9]{2}[\\s\u3000]+([1-6])[\\s\u3000]")
TRI_RE = re.compile("^\\s+\uff13\u9023\u5358[\\s\u3000]+([1-6]-[1-6]-[1-6])[\\s\u3000]+([0-9]+)[\\s\u3000]+\u4eba\u6c17[\\s\u3000]+([0-9]+)")
TOKS_RE = re.compile("[\\s\u3000]+")
ROWCOLS = ["hd", "jcd", "rno", "kim", "pay", "c1", "c2", "c3", "c4", "c5", "c6",
           "w1", "w2", "w3", "w4", "w5", "w6", "winC", "winW"]


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
        winc = 0
        winw = 0
        for chaku, waku, toban, shin in cur["e"]:
            byw[waku] = toban
            if shin:
                byc[shin] = toban
            if chaku in ("01", "1"):
                winw = waku
                winc = shin or 0
        row = [hd, jcd, cur["rno"], cur["kim"], cur["pay"]]
        row += [byc.get(c, "") for c in range(1, 7)]
        row += [byw.get(k, "") for k in range(1, 7)]
        row += [winc, winw]
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
            cur = {"rno": int(h.group(1)), "kim": "", "pay": "", "e": []}
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
            cur["e"].append((e.group(1), int(e.group(2)), e.group(3), int(m2.group(1)) if m2 else 0))
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
                             int(r["c1"] or 0)] + cc + wc)
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
    print("analyze OK races=%d main=%.4f mde=%.4f" % (int(H14.sum()), s1["main"]["diffPt"], s1["main"]["mdePt"]))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "rows":
        if sys.argv[2] not in YEARS:
            stop("年は 2016 から 2026")
        run_rows(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "analyze":
        run_analyze()
    else:
        stop("使い方：rows YYYY ／ analyze")


if __name__ == "__main__":
    main()
