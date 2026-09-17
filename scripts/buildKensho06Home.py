# -*- coding: utf-8 -*-
# buildKensho06Home.py
# 検証06「地元選手は強いのか」。
# 番組表（Bファイル）の支部と、競走成績（Kファイル）の着順・進入を
# 日付・場コード・R・登番で突き合わせ、地元（選手の支部＝開催場の所在地支部）の
# 成績差を、統制なし → レース内シャッフル → 分解 → 個体内 → 検出力 の順に数える。
#
# 入力（すべて読み取り専用・リポジトリ外）:
#   C:\Users\USER\bfiles\YYYYMM\bYYMMDD.lzh      番組表（cp932）
#   C:\Users\USER\boatrace\data\kfiles\kYYMMDD.lzh 競走成績（cp932）
# 中間物（リポジトリに入れない）: 第2引数の作業ディレクトリ
# 出力: analysis/kensho06/ summary.json / strataCourseRank.csv / withinRacer.csv / power.csv
#
# 使い方:
#   py -3 scripts/buildKensho06Home.py extract <作業ディレクトリ>
#   py -3 scripts/buildKensho06Home.py stage0  <作業ディレクトリ>
#   py -3 scripts/buildKensho06Home.py stage1-8 <作業ディレクトリ>
import os
import re
import sys
import csv
import json
import math
import datetime
import unicodedata
import collections
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

BDIR = r"C:\Users\USER\bfiles"
KDIR = r"C:\Users\USER\boatrace\data\kfiles"
OUTDIR = os.path.join(ROOT, "analysis", "kensho06")

WIN_FROM = datetime.date(2016, 11, 1)
WIN_TO = datetime.date(2026, 8, 11)   # B の実在庫の終わり（裁定2）

SEED = 20260917
NREP = 1000
NMIN = 300
Z = 1.959963984540054        # 両側95%
Z_BETA = 0.8416212335729143  # 検出力0.8
DELTA = 0.02                 # 検出したい1着率の差

BRANCH18 = ["群馬", "埼玉", "東京", "静岡", "愛知", "三重", "福井", "滋賀", "大阪",
            "兵庫", "徳島", "香川", "岡山", "広島", "山口", "福岡", "佐賀", "長崎"]
RANKS = ["A1", "A2", "B1", "B2"]

# 場→所在地支部（裁定1：外から与える正本。データからは導かない）
VENUE_BRANCH = {
    "01": ("桐生", "群馬"), "02": ("戸田", "埼玉"), "03": ("江戸川", "東京"), "04": ("平和島", "東京"),
    "05": ("多摩川", "東京"), "06": ("浜名湖", "静岡"), "07": ("蒲郡", "愛知"), "08": ("常滑", "愛知"),
    "09": ("津", "三重"), "10": ("三国", "福井"), "11": ("びわこ", "滋賀"), "12": ("住之江", "大阪"),
    "13": ("尼崎", "兵庫"), "14": ("鳴門", "徳島"), "15": ("丸亀", "香川"), "16": ("児島", "岡山"),
    "17": ("宮島", "広島"), "18": ("徳山", "山口"), "19": ("下関", "山口"), "20": ("若松", "福岡"),
    "21": ("芦屋", "福岡"), "22": ("福岡", "福岡"), "23": ("唐津", "佐賀"), "24": ("大村", "長崎"),
}

B_ENTRY = re.compile(rb"^[1-6] \d{4}")
B_RACE = re.compile(r"^[\s\u3000]*(\d{1,2})R")


# ---------------------------------------------------------------- 抽出

def dates():
    d = WIN_FROM
    while d <= WIN_TO:
        yield d
        d += datetime.timedelta(1)


def read_lzh(path):
    import lhafile
    a = lhafile.Lhafile(path)
    names = a.namelist()
    return b"".join(a.read(n) for n in names), len(names)


def parse_b(d):
    """1日分の番組表 → 選手行のリスト。ファイルが無ければ None"""
    sys.path.insert(0, BDIR)
    ymd = d.strftime("%y%m%d")
    path = os.path.join(BDIR, d.strftime("%Y%m"), "b" + ymd + ".lzh")
    if not os.path.exists(path):
        return d.isoformat(), None, []
    raw, _ = read_lzh(path)
    rows = []
    bad = []
    jcd = None
    rno = None
    for l in raw.split(b"\r\n"):
        m = re.match(rb"^(\d{2})BBGN", l)
        if m:
            jcd = m.group(1).decode()
            rno = None
            continue
        if re.match(rb"^\d{2}BEND", l):
            jcd = None
            continue
        if jcd is None:
            continue
        if B_ENTRY.match(l):
            if len(l) < 24 or rno is None:
                bad.append((jcd, rno, l.decode("cp932", "replace")))
                continue
            rows.append((d.isoformat(), jcd, rno, int(l[0:1]), l[2:6].decode(),
                         l[6:14].decode("cp932", "replace"),
                         l[14:16].decode("cp932", "replace"),
                         l[16:20].decode("cp932", "replace"),
                         l[20:22].decode("cp932", "replace"),
                         l[22:24].decode("cp932", "replace"),
                         l.decode("cp932", "replace")))
            continue
        try:
            t = unicodedata.normalize("NFKC", l.decode("cp932"))
        except UnicodeDecodeError:
            continue
        rm = B_RACE.match(t)
        if rm and ("締切" in t or "H" in t):
            rno = int(rm.group(1))
    return d.isoformat(), rows, bad


def parse_k(d):
    import kparser
    sys.path.insert(0, BDIR)
    ymd = d.strftime("%y%m%d")
    path = os.path.join(KDIR, "k" + ymd + ".lzh")
    if not os.path.exists(path):
        return d.isoformat(), None, [], []
    raw, _ = read_lzh(path)
    text = raw.decode("cp932", "replace").replace("\r\n", "\n")
    res = kparser.parse_day(text, d.isoformat())
    kim = {(r["jcd"], r["rno"]): r["kimarite"] for r in res["races"]}
    rows = [(e["hd"], e["jcd"], e["rno"], e["waku"], e["toban"], e["chaku"],
             e["shinnyu"], e["st"], kim.get((e["jcd"], e["rno"]), ""))
            for e in res["entries"]]
    races = [(r["hd"], r["jcd"], r["rno"]) for r in res["races"]]
    return d.isoformat(), rows, races, res["anomalies"]


def extract(work):
    ds = list(dates())
    with Pool(8) as p:
        bres = p.map(parse_b, ds, chunksize=16)
        kres = p.map(parse_k, ds, chunksize=16)
    miss_b = [x[0] for x in bres if x[1] is None]
    miss_k = [x[0] for x in kres if x[1] is None]
    with open(os.path.join(work, "bRows.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "jcd", "rno", "waku", "toban", "name", "age", "branch",
                    "weight", "rank", "raw"])
        for x in bres:
            for r in (x[1] or []):
                w.writerow(r)
    with open(os.path.join(work, "bBad.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for x in bres:
            for r in x[2]:
                w.writerow((x[0],) + tuple(r))
    with open(os.path.join(work, "kRows.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "jcd", "rno", "waku", "toban", "chaku", "course", "st", "kimarite"])
        for x in kres:
            for r in (x[1] or []):
                w.writerow(r)
    with open(os.path.join(work, "kRaces.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for x in kres:
            for r in x[2]:
                w.writerow(r)
    with open(os.path.join(work, "kAnom.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for x in kres:
            for a in x[3]:
                w.writerow([a["hd"], a["jcd"], a["rno"], a["種別"], a["生行"]])
    json.dump({"missingB": miss_b, "missingK": miss_k},
              open(os.path.join(work, "missing.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("B rows", sum(len(x[1] or []) for x in bres), "K rows",
          sum(len(x[1] or []) for x in kres), "missB", len(miss_b), "missK", len(miss_k))


# ---------------------------------------------------------------- 共通

# Kファイルの着欄 → 着コード（REFERENCE.md の 1〜16 体系）への対応。
# 01〜06=着順 / F=14 / L0,L1=15 / K0,K1=16(欠場) / S0,S1,S2=失格系(7〜13 のどれかだが K では区別不能)
# "00" は不成立レース（1着の無いレース）の残り艇。着順ではないのでレースごと除く（stage0 で件数を出す）
CHAKU_FINISH = {"01": 1, "02": 2, "03": 3, "04": 4, "05": 5, "06": 6}
CHAKU_ROUND6 = {"F": 14, "L0": 15, "L1": 15, "S0": 13, "S1": 13, "S2": 13}
CHAKU_ABSENT = {"K0", "K1"}

# 地区（stage6 の「近接」）。支部→地区の対応はデータに無いので、
# ボートレースの6地区区分を使う（場→支部は裁定1の VENUE_BRANCH）
DISTRICT = {"群馬": "関東", "埼玉": "関東", "東京": "関東",
            "静岡": "東海", "愛知": "東海", "三重": "東海",
            "福井": "近畿", "滋賀": "近畿", "大阪": "近畿", "兵庫": "近畿",
            "徳島": "四国", "香川": "四国",
            "岡山": "中国", "広島": "中国", "山口": "中国",
            "福岡": "九州", "佐賀": "九州", "長崎": "九州"}

AGE_BANDS = [(0, 29, "〜29"), (30, 39, "30〜39"), (40, 49, "40〜49"), (50, 99, "50〜")]


def jst_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime(
        "%Y-%m-%d %H:%M JST")


def wilson(k, n):
    if n < NMIN:
        return None
    p = k / n
    den = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / den
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return {"rate": round(p, 6), "lo": round(c - h, 6), "hi": round(c + h, 6), "n": int(n)}


def meanci(s, s2, n):
    """平均着の区間（Wilson は率にしか使えないので、平均±1.96SE）"""
    if n < NMIN:
        return None
    m = s / n
    var = max(s2 / n - m * m, 0.0) * n / (n - 1)
    se = math.sqrt(var / n)
    return {"mean": round(m, 6), "lo": round(m - Z * se, 6), "hi": round(m + Z * se, 6), "n": int(n)}


def rates(D, mask):
    n = int(mask.sum())
    if n < NMIN:
        return {"n": n, "note": "n不足"}
    f = D["fin"][mask].astype(np.float64)
    return {"n": n,
            "win": wilson(int((f == 1).sum()), n),
            "top3": wilson(int((f <= 3).sum()), n),
            "meanFinish": meanci(float(f.sum()), float((f * f).sum()), n)}


def load_summary():
    p = os.path.join(OUTDIR, "summary.json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {}


def save_summary(s):
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
        f.write("\n")


def stop(summary, msg):
    summary.setdefault("stopped", []).append({"at": jst_now(), "reason": msg})
    save_summary(summary)
    print("STOP:", msg)
    sys.exit(1)


def load(work):
    z = np.load(os.path.join(work, "analysis.npz"))
    return {k: z[k] for k in z.files}


# ---------------------------------------------------------------- stage0

def stage0(work):
    import pandas as pd
    s = {}
    s["meta"] = {"script": "scripts/buildKensho06Home.py", "python": sys.version.split()[0],
                 "numpy": np.__version__, "pandas": pd.__version__,
                 "runStartedJST": jst_now(), "seed": SEED, "reps": NREP,
                 "window": [WIN_FROM.isoformat(), WIN_TO.isoformat()],
                 "input": "C:\\Users\\USER\\bfiles（番組表）/ C:\\Users\\USER\\boatrace\\data\\kfiles（競走成績）。どちらも読み取りのみ",
                 "intermediate": "scratchpad のみ（リポジトリに入れない）"}
    miss = json.load(open(os.path.join(work, "missing.json"), encoding="utf-8"))
    b = pd.read_csv(os.path.join(work, "bRows.csv"), dtype=str, keep_default_na=False,
                    usecols=["date", "jcd", "rno", "waku", "toban", "age", "branch", "weight", "rank"])
    k = pd.read_csv(os.path.join(work, "kRows.csv"), dtype=str, keep_default_na=False)
    kr = pd.read_csv(os.path.join(work, "kRaces.csv"), dtype=str, keep_default_na=False,
                     header=None, names=["date", "jcd", "rno"])
    with open(os.path.join(work, "bBad.csv"), encoding="utf-8") as f:
        bBad = sum(1 for _ in f)
    kAnom = pd.read_csv(os.path.join(work, "kAnom.csv"), dtype=str, keep_default_na=False,
                        header=None, names=["date", "jcd", "rno", "type", "raw"])

    key = ["date", "jcd", "rno", "toban"]
    kr_dup = int(kr.duplicated().sum())
    m = b.merge(k, on=key, how="outer", suffixes=("_b", "_k"), indicator=True)
    both = (m["_merge"] == "both").to_numpy()
    bonly = m[m["_merge"] == "left_only"]
    konly = m[m["_merge"] == "right_only"]

    kdays, bdays = set(k["date"]), set(b["date"])
    kven, bven = set(zip(k["date"], k["jcd"])), set(zip(b["date"], b["jcd"]))
    krace = set(zip(k["date"], k["jcd"], k["rno"]))
    brace = set(zip(b["date"], b["jcd"], b["rno"]))
    kwaku = set(zip(k["date"], k["jcd"], k["rno"], k["waku"]))
    bwaku = set(zip(b["date"], b["jcd"], b["rno"], b["waku"]))

    def reason_b(r):
        if r.date not in kdays:
            return "Kにその日が無い"
        if (r.date, r.jcd) not in kven:
            return "Kにその場が無い"
        if (r.date, r.jcd, r.rno) not in krace:
            return "KにそのRが無い"
        if (r.date, r.jcd, r.rno, r.waku_b) in kwaku:
            return "登番不一致（同じ枠にKでは別の登番）"
        return "Kのそのレースにその枠の行が無い"

    def reason_k(r):
        if r.date not in bdays:
            return "Bにその日が無い"
        if (r.date, r.jcd) not in bven:
            return "Bにその場が無い"
        if (r.date, r.jcd, r.rno) not in brace:
            return "BにそのRが無い"
        if (r.date, r.jcd, r.rno, r.waku_k) in bwaku:
            return "登番不一致（同じ枠にBでは別の登番）"
        return "Bのそのレースにその枠の行が無い"

    rb = collections.Counter(reason_b(r) for r in bonly.itertuples())
    rk = collections.Counter(reason_k(r) for r in konly.itertuples())
    nB, nK, nM = len(b), len(k), int(both.sum())
    rateB, rateK = nM / nB, nM / nK

    mm = bonly.merge(konly, left_on=["date", "jcd", "rno", "waku_b"],
                     right_on=["date", "jcd", "rno", "waku_k"], suffixes=("B", "K"))
    mismatchEx = [{"date": r.date, "jcd": r.jcd, "rno": r.rno, "waku": r.waku_bB,
                   "tobanB": r.tobanB, "tobanK": r.tobanK} for r in mm.head(5).itertuples()]

    # 支部
    bc = b["branch"].value_counts()
    b18 = {x: int(bc.get(x, 0)) for x in BRANCH18}
    other = b[~b["branch"].isin(BRANCH18)]
    otherEx = []
    if len(other):
        want = set(zip(other["date"].head(5), other["jcd"].head(5), other["rno"].head(5),
                       other["toban"].head(5)))
        with open(os.path.join(work, "bRows.csv"), encoding="utf-8") as f:
            for row in csv.reader(f):
                if (row[0], row[1], row[2], row[4]) in want:
                    otherEx.append(row[10])
    otherRate = len(other) / nB

    # 場→支部の検算（正本は VENUE_BRANCH。B の全選手行で「全国シェアに対する倍率」が最大の支部と突き合わせる）
    nat = b["branch"].value_counts(normalize=True)
    venueCheck = {}
    liftMismatch = []
    for jcd, g in b.groupby("jcd"):
        sh = g["branch"].value_counts(normalize=True)
        lift = (sh / nat.reindex(sh.index)).sort_values(ascending=False)
        name, br = VENUE_BRANCH[jcd]
        venueCheck[jcd] = {"venue": name, "branch": br,
                           "branchByLift": lift.index[0], "lift": round(float(lift.iloc[0]), 3),
                           "secondLift": [lift.index[1], round(float(lift.iloc[1]), 3)],
                           "branchByShare": sh.index[0], "share": round(float(sh.iloc[0]), 4),
                           "rows": int(len(g)), "match": bool(lift.index[0] == br)}
        if lift.index[0] != br:
            liftMismatch.append(jcd)
    liftMatch = sum(1 for v in venueCheck.values() if v["match"])
    vbmap = {j: VENUE_BRANCH[j][1] for j in sorted(VENUE_BRANCH)}

    # 不成立レース（1着が無い）
    firsts = k.assign(is1=(k["chaku"] == "01")).groupby(["date", "jcd", "rno"])["is1"].sum()
    voidRaces = firsts[firsts == 0]

    races_m = m.loc[both, ["date", "jcd", "rno"]].drop_duplicates()
    byYear = {}
    for y in range(2016, 2027):
        ys = str(y)
        byYear[ys] = {"racesB": sum(1 for r in brace if r[0][:4] == ys),
                      "racesK": sum(1 for r in krace if r[0][:4] == ys),
                      "racesMatched": int((races_m["date"].str[:4] == ys).sum())}
    months = collections.defaultdict(lambda: [0, 0, 0])
    for d in dates():
        months[d.strftime("%Y-%m")][0] += 1
    for d in bdays:
        months[d[:7]][1] += 1
    for d in kdays:
        months[d[:7]][2] += 1
    gapMonths = [{"month": mo, "calendarDays": v[0], "bDays": v[1], "kDays": v[2]}
                 for mo, v in sorted(months.items()) if v[1] < v[0] or v[2] < v[0]]

    s["venueBranch"] = vbmap
    s["stage0"] = {
        "days": {"calendar": sum(1 for _ in dates()), "bDays": len(bdays), "kDays": len(kdays),
                 "bothDays": len(bdays & kdays),
                 "missingBDates": miss["missingB"], "missingKDates": miss["missingK"]},
        "races": {"b": len(brace), "k": len(krace), "matched": int(len(races_m)),
                  "kRaceListDuplicates": kr_dup, "voidRacesNoFirst": int(len(voidRaces))},
        "starts": {"bRows": nB, "kRows": nK, "matched": nM,
                   "matchRateOfB": round(rateB, 6), "matchRateOfK": round(rateK, 6)},
        "unmatched": {"bOnly": int(len(bonly)), "bOnlyNote": "理由未確認（機械的な区分のみ）", "bOnlyReasons": dict(rb),
                      "kOnly": int(len(konly)), "kOnlyReasons": dict(rk),
                      "tobanMismatchExamples": mismatchEx},
        "parse": {"bEntryLinesUnparsed": bBad,
                  "kAnomalies": {t: int(v) for t, v in kAnom["type"].value_counts().items()}},
        "chakuRawCounts": {c: int(v) for c, v in k["chaku"].value_counts().items()},
        "chakuMapping": "01〜06→着順 / F→14 / L0,L1→15 / S0,S1,S2→失格系(7〜13) / K0,K1→16(欠場)。"
                        "7〜15 は6に丸め、16 は分母から除く。\"00\" は1着の無い不成立レースの残り艇で、そのレースごと除く",
        "branch18": b18,
        "branchOther": {"rows": int(len(other)), "rateOfB": round(otherRate, 8),
                        "values": {str(x): int(v) for x, v in other["branch"].value_counts().items()},
                        "examples": otherEx},
        "venueToBranch": venueCheck,
        "venueToBranchDefinition": "所在地支部は裁定1の表（スクリプトの VENUE_BRANCH）が正本。"
                                   "検算として、B の全選手行で場ごとに全国シェアに対する倍率が最大の支部と突き合わせた",
        "liftCheck": {"matchedVenues": liftMatch, "mismatchVenues": liftMismatch},
        "kRowsAfterWindowEnd": int((k["date"] > WIN_TO.isoformat()).sum()),
        "kOnlyNoBDay": int(rk.get("Bにその日が無い", 0)),
        "byYear": byYear,
        "gapMonths": gapMonths,
    }

    s["meta"]["runFinishedJST"] = jst_now()
    save_summary(s)
    if rateB < 0.95 or rateK < 0.95:
        stop(s, "B・K の突合率が95%%を下回った（B基準 %.4f / K基準 %.4f）" % (rateB, rateK))
    if otherRate > 0.001:
        stop(s, "支部18種以外が0.1%%を超えた（%.5f）" % otherRate)
    if liftMatch < 23:
        stop(s, "裁定1の表と倍率最大の支部の一致が23場未満（%d場。不一致 %s）" % (liftMatch, liftMismatch))

    # 解析用データ（scratchpad）
    a = m[both]
    n00 = int((a["chaku"] == "00").sum())
    vidx = pd.MultiIndex.from_frame(a[["date", "jcd", "rno"]])
    a = a[~vidx.isin(voidRaces.index)]
    n_void_rows = int(nM - len(a))
    absent = a["chaku"].isin(CHAKU_ABSENT)
    n_absent = int(absent.sum())
    a = a[~absent]
    unknown_chaku = a[~a["chaku"].isin(list(CHAKU_FINISH) + list(CHAKU_ROUND6))]
    n_other_branch = int((~a["branch"].isin(BRANCH18)).sum())
    a = a[a["branch"].isin(BRANCH18)]
    a = a.sort_values(["date", "jcd", "rno", "waku_k"]).reset_index(drop=True)
    fin = a["chaku"].map(lambda c: CHAKU_FINISH.get(c, 6)).astype(np.int8).to_numpy()
    rid = a.groupby(["date", "jcd", "rno"], sort=False).ngroup().to_numpy().astype(np.int64)
    pos = a.groupby(rid).cumcount().to_numpy().astype(np.int64)
    bidx = a["branch"].map({x: i for i, x in enumerate(BRANCH18)}).to_numpy().astype(np.int8)
    jcd = a["jcd"].astype(int).to_numpy().astype(np.int8)
    vb = np.array([BRANCH18.index(vbmap["%02d" % j]) if "%02d" % j in vbmap else -1
                   for j in range(25)], dtype=np.int8)
    home = bidx == vb[jcd]
    course = pd.to_numeric(a["course"], errors="coerce").fillna(0).astype(np.int8).to_numpy()
    rank = a["rank"].map({x: i for i, x in enumerate(RANKS)}).fillna(-1).astype(np.int8).to_numpy()
    age = pd.to_numeric(a["age"], errors="coerce").fillna(-1).astype(np.int16).to_numpy()
    year = a["date"].str[:4].astype(int).to_numpy().astype(np.int16)
    dnum = (pd.to_datetime(a["date"]) - pd.Timestamp("2016-01-01")).dt.days.to_numpy().astype(np.int32)
    toban = a["toban"].astype(int).to_numpy().astype(np.int32)
    np.savez(os.path.join(work, "analysis.npz"), rid=rid, pos=pos, bidx=bidx, jcd=jcd, home=home,
             course=course, rank=rank, age=age, year=year, dnum=dnum, toban=toban, fin=fin, vb=vb)
    s["stage0"]["analysisSet"] = {
        "matchedRows": nM, "removedVoidRaces": int(len(voidRaces)), "chaku00RowsInMatched": n00,
        "removedVoidRaceRows": n_void_rows, "removedAbsent16": n_absent,
        "removedBranchOther": n_other_branch, "rows": int(len(a)), "races": int(rid.max() + 1),
        "unknownChakuRows": int(len(unknown_chaku)),
        "rankOther": int((rank < 0).sum()), "courseUnknown": int((course == 0).sum()),
        "ageUnreadable": int((age < 0).sum()), "homeRows": int(home.sum()),
        "homeShare": round(float(home.mean()), 6),
    }
    s["meta"]["runFinishedJST"] = jst_now()
    save_summary(s)
    print(json.dumps({k2: s["stage0"][k2] for k2 in ["days", "races", "starts", "unmatched", "branchOther",
                                                      "liftCheck", "analysisSet", "gapMonths"]},
                     ensure_ascii=False, indent=1))
    if len(unknown_chaku):
        stop(s, "想定外の着記号が残った: %s" % unknown_chaku["chaku"].value_counts().to_dict())


# ---------------------------------------------------------------- 共通（stage1〜）

YEARS = list(range(2016, 2027))
METRICS = [("win", "rate"), ("top3", "rate"), ("meanFinish", "mean")]


def val(r, m):
    x = r.get(m) if isinstance(r, dict) else None
    return None if x is None else x["rate" if m != "meanFinish" else "mean"]


def diff3(a, b):
    out = {}
    for m, _ in METRICS:
        va, vb = val(a, m), val(b, m)
        out[m] = None if va is None or vb is None else round(va - vb, 6)
    return out


def district_of(D):
    dist = {d: i for i, d in enumerate(["関東", "東海", "近畿", "四国", "中国", "九州"])}
    bd = np.array([dist[DISTRICT[x]] for x in BRANCH18], dtype=np.int8)
    return bd[D["bidx"]], bd[D["vb"][D["jcd"]]]


def ymd(dnum):
    return (datetime.date(2016, 1, 1) + datetime.timedelta(int(dnum))).isoformat()


# ---------------------------------------------------------------- stage1

def stage1(work):
    D = load(work)
    s = load_summary()
    h = D["home"]
    home, non = rates(D, h), rates(D, ~h)
    s["stage1"] = {"note": "結論ではない。統制なしで「そう見えた」を再現する段",
                   "home": home, "nonHome": non, "diffHomeMinusNon": diff3(home, non)}
    save_summary(s)
    print(json.dumps(s["stage1"], ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- stage2

MASK64 = (1 << 64) - 1


def splitmix(x):
    x = x + np.uint64(0x9E3779B97F4A7C15)
    x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def splitmix_int(x):
    x = (x + 0x9E3779B97F4A7C15) & MASK64
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & MASK64
    return x ^ (x >> 31)


def shuffle_reps(D, r0, r1):
    """rep r0..r1-1 のレース内シャッフル。乱数は (seed+レース通番, 枠内の位置, rep) だけから決まる"""
    rid = D["rid"]
    home = D["home"]
    fin = D["fin"]
    win = fin == 1
    top3 = fin <= 3
    fin64 = fin.astype(np.int64)
    yi = (D["year"] - 2016).astype(np.int64)
    vi = (D["jcd"].astype(np.int64) - 1)
    course = D["course"].astype(np.int64)
    with np.errstate(over="ignore"):
        base = splitmix(splitmix(np.uint64(SEED) + rid.astype(np.uint64)) ^ D["pos"].astype(np.uint64))
    ridf = rid.astype(np.float64)
    hcount = np.bincount(rid[home], minlength=int(rid.max()) + 1)
    R = r1 - r0
    out = {"all": np.zeros((R, 3)), "year": np.zeros((R, 3, 11)), "venue": np.zeros((R, 3, 24)),
           "homeCourse": np.zeros((R, 7), dtype=np.int64), "raceHomeCountOk": np.zeros(R, dtype=bool)}
    for i, rep in enumerate(range(r0, r1)):
        with np.errstate(over="ignore"):
            u = splitmix(base ^ np.uint64(splitmix_int(rep + 1)))
        key = ridf + (u >> np.uint64(11)).astype(np.float64) * (2.0 ** -53)
        order = np.argsort(key, kind="stable")
        idx = np.flatnonzero(home[order])  # 行 k にはレース内で並べ替えた先の行のラベルが付く
        w, t, f = win[idx], top3[idx], fin64[idx]
        out["all"][i] = (w.sum(), t.sum(), f.sum())
        for j, arr in enumerate((w, t, f)):
            out["year"][i, j] = np.bincount(yi[idx], weights=arr, minlength=11)
            out["venue"][i, j] = np.bincount(vi[idx], weights=arr, minlength=24)
        out["homeCourse"][i] = np.bincount(course[idx], minlength=7)
        out["raceHomeCountOk"][i] = np.array_equal(np.bincount(rid[idx], minlength=len(hcount)), hcount)
    return out


def sums_to_diff(hs, tot_s, n_h, n_t):
    """地元側の合計 hs と全体合計から、地元−非地元 の差（率または平均）"""
    return hs / n_h - (tot_s - hs) / (n_t - n_h)


def pnull(obs, null):
    mu = null.mean()
    return float((1 + np.sum(np.abs(null - mu) >= abs(obs - mu) - 1e-12)) / (len(null) + 1))


def nullstat(obs, null):
    return {"observed": round(float(obs), 6), "nullMean": round(float(null.mean()), 6),
            "null95": [round(float(np.quantile(null, 0.025)), 6), round(float(np.quantile(null, 0.975)), 6)],
            "excess": round(float(obs - null.mean()), 6), "p": round(pnull(obs, null), 6)}


def stage2(work):
    import time
    D = load(work)
    s = load_summary()
    t0 = time.time()
    full = shuffle_reps(D, 0, NREP)
    t1 = time.time()
    np.savez(os.path.join(work, "null.npz"), **full)
    a = shuffle_reps(D, 0, NREP // 2)
    b = shuffle_reps(D, NREP // 2, NREP)
    t2 = time.time()
    same = all(np.array_equal(full[k], np.concatenate([a[k], b[k]])) for k in full)

    home = D["home"]
    fin = D["fin"].astype(np.int64)
    obs_s = np.array([(fin[home] == 1).sum(), (fin[home] <= 3).sum(), fin[home].sum()], dtype=np.float64)
    tot_s = np.array([(fin == 1).sum(), (fin <= 3).sum(), fin.sum()], dtype=np.float64)
    nH, nT = int(home.sum()), len(fin)
    res = {}
    for j, (m, _) in enumerate(METRICS):
        obs = sums_to_diff(obs_s[j], tot_s[j], nH, nT)
        null = sums_to_diff(full["all"][:, j], tot_s[j], nH, nT)
        res[m] = nullstat(obs, null)
    course = D["course"].astype(np.int64)
    obsCourse = np.bincount(course[home], minlength=7)
    allCourse = np.bincount(course, minlength=7)
    s["stage2"] = {
        "definition": "同一レース内で支部ラベル（＝地元フラグ）だけを並べ替える。進入コース・着は動かさない。"
                      "乱数は splitmix64 で (seed %d + レース通番, 枠内の位置, rep) から決める。"
                      "p は帰無平均からの絶対偏差で数えた両側 (1+#)/(1+%d)" % (SEED, NREP),
        "reps": NREP, "nHome": nH, "nAll": nT,
        "stats": res,
        "courseCheck": {
            "allRowsCourseCounts": {str(c): int(allCourse[c]) for c in range(7)},
            "allRowsCourseNote": "進入コース列は並べ替えの対象外（配列を変更していない）ので全行のコース分布は全repで同一",
            "homeCountPerRaceUnchangedAllReps": bool(full["raceHomeCountOk"].all()),
            "homeLabeledCourseObserved": {str(c): int(obsCourse[c]) for c in range(7)},
            "homeLabeledCourseNullMean": {str(c): round(float(full["homeCourse"][:, c].mean()), 2) for c in range(7)},
            "homeLabeledCourseTotalEqualAllReps": bool((full["homeCourse"].sum(axis=1) == nH).all()),
        },
        "partitionInvariance": {"split": "reps 1〜500 と 501〜1000 を別呼び出しで実行し、一括 1〜1000 と全配列が完全一致するか",
                                "identical": bool(same)},
        "seconds": {"full": round(t1 - t0, 1), "split": round(t2 - t1, 1)},
    }
    save_summary(s)
    print(json.dumps(s["stage2"], ensure_ascii=False, indent=1))
    if not same:
        stop(s, "stage2 の分割不変の確認が一致しなかった")


# ---------------------------------------------------------------- stage3

FACTORS = ["venue", "rank", "course", "age", "starts"]
FACTOR_JA = {"venue": "場の違い", "rank": "級別の偏り", "course": "進入コースの偏り",
             "age": "年齢の偏り", "starts": "出走数の偏り", "residual": "残り"}
FACTOR_COLS = {"venue": range(2, 25), "rank": range(25, 28), "course": range(28, 34),
               "age": range(34, 37), "starts": range(37, 40)}


def starts_band(D):
    ry = D["toban"].astype(np.int64) * 10000 + D["year"].astype(np.int64)
    u, inv, cnt = np.unique(ry, return_inverse=True, return_counts=True)
    q = np.quantile(cnt, [0.25, 0.5, 0.75])
    return np.digitize(cnt[inv], q, right=True).astype(np.int8), q


def age_band(D):
    a = D["age"]
    return np.select([a <= 29, a <= 39, a <= 49], [0, 1, 2], 3).astype(np.int8)


def design(D, sl, ab, sb):
    n = sl.stop - sl.start
    X = np.zeros((n, 40))
    X[:, 0] = 1
    X[:, 1] = D["home"][sl]
    r = np.arange(n)
    j = D["jcd"][sl].astype(np.int64)
    m = j >= 2
    X[r[m], 2 + j[m] - 2] = 1                      # 場 02〜24（01 が基準）
    k = D["rank"][sl].astype(np.int64)
    m = k >= 1
    X[r[m], 25 + k[m] - 1] = 1                     # A2,B1,B2（A1 が基準）
    c = D["course"][sl].astype(np.int64)
    cc = np.where(c == 0, 6, c - 1)                # 1コースが基準 / 2..6 / 不明
    m = cc >= 1
    X[r[m], 28 + cc[m] - 1] = 1
    a = ab[sl].astype(np.int64)
    m = a >= 1
    X[r[m], 34 + a[m] - 1] = 1
    b = sb[sl].astype(np.int64)
    m = b >= 1
    X[r[m], 37 + b[m] - 1] = 1
    return X


def decompose(XtX, Xty, sH, sN, nH, nN, yH, yN):
    beta = np.linalg.lstsq(XtX, Xty, rcond=None)[0]
    dx = sH / nH - sN / nN
    raw = yH / nH - yN / nN
    out = {}
    for f, cols in FACTOR_COLS.items():
        cols = list(cols)
        out[f] = float(dx[cols] @ beta[cols])
    out["residual"] = float(beta[1])
    out["raw"] = float(raw)
    out["closure"] = float(raw - sum(out[f] for f in FACTOR_COLS) - beta[1])
    return out


def stage3(work):
    D = load(work)
    s = load_summary()
    ab = age_band(D)
    sb, q = starts_band(D)
    fin = D["fin"].astype(np.float64)
    Y = np.stack([(fin == 1).astype(np.float64), (fin <= 3).astype(np.float64), fin], axis=1)
    year = D["year"]
    acc = {}
    for y in YEARS:
        idx = np.flatnonzero(year == y)
        if len(idx) == 0:
            continue
        lo, hi = int(idx[0]), int(idx[-1]) + 1
        assert hi - lo == len(idx)
        XtX = np.zeros((40, 40))
        Xty = np.zeros((40, 3))
        sH = np.zeros(40)
        sN = np.zeros(40)
        yH = np.zeros(3)
        yN = np.zeros(3)
        for st in range(lo, hi, 300000):
            sl = slice(st, min(st + 300000, hi))
            X = design(D, sl, ab, sb)
            h = D["home"][sl]
            XtX += X.T @ X
            Xty += X.T @ Y[sl]
            sH += X[h].sum(axis=0)
            sN += X[~h].sum(axis=0)
            yH += Y[sl][h].sum(axis=0)
            yN += Y[sl][~h].sum(axis=0)
        acc[y] = [XtX, Xty, sH, sN, yH, yN, int(D["home"][lo:hi].sum()), int((~D["home"][lo:hi]).sum())]
    tot = [sum(a[i] for a in acc.values()) for i in range(8)]
    res = {}
    byYear = {}
    unstable = []
    for j, (m, _) in enumerate(METRICS):
        o = decompose(tot[0], tot[1][:, j], tot[2], tot[3], tot[6], tot[7], tot[4][j], tot[5][j])
        res[m] = {"raw": round(o["raw"], 6), "closureError": o["closure"], "parts": {}}
        for f in FACTORS + ["residual"]:
            res[m]["parts"][FACTOR_JA[f]] = {"value": round(o[f], 6), "pctOfRaw": round(100 * o[f] / o["raw"], 1)}
        byYear[m] = {}
        signs = collections.defaultdict(list)
        for y, a in acc.items():
            oy = decompose(a[0], a[1][:, j], a[2], a[3], a[6], a[7], a[4][j], a[5][j])
            byYear[m][str(y)] = {FACTOR_JA.get(k2, k2): round(v, 6) for k2, v in oy.items() if k2 != "closure"}
            for f in FACTORS + ["residual"]:
                signs[f].append(np.sign(oy[f]))
        for f in FACTORS + ["residual"]:
            ov = np.sign(o[f])
            nd = sum(1 for x in signs[f] if x != ov)
            if nd:
                unstable.append({"metric": m, "item": FACTOR_JA[f], "overallSign": int(ov),
                                 "yearsWithOtherSign": nd, "years": len(signs[f])})

    rows = []
    course, rank, home = D["course"], D["rank"], D["home"]
    for c in range(1, 7):
        for k, rk in enumerate(RANKS):
            cell = (course == c) & (rank == k)
            H = rates(D, cell & home)
            N = rates(D, cell & ~home)
            dd = diff3(H, N)
            row = {"course": c, "rank": rk, "nHome": H["n"], "nNon": N["n"], "nTotal": H["n"] + N["n"]}
            for m, _ in METRICS:
                for side, R in (("Home", H), ("Non", N)):
                    x = R.get(m) if "note" not in R else None
                    row[m + side] = "" if x is None else x["rate" if m != "meanFinish" else "mean"]
                    row[m + side + "Lo"] = "" if x is None else x["lo"]
                    row[m + side + "Hi"] = "" if x is None else x["hi"]
                row[m + "Diff"] = "" if dd[m] is None else dd[m]
            row["note"] = "" if (H["n"] >= NMIN and N["n"] >= NMIN) else "n不足"
            rows.append(row)
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "strataCourseRank.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if r["note"] == ""]
    cellInfo = {"cells": len(rows), "medianNTotal": float(np.median([r["nTotal"] for r in rows])),
                "cellsBothSidesN300": len(ok),
                "cellsTotalN300": sum(1 for r in rows if r["nTotal"] >= NMIN),
                "courseUnknownRowsExcluded": int((course == 0).sum()),
                "diffRange": {m: ([min(r[m + "Diff"] for r in ok), max(r[m + "Diff"] for r in ok)] if ok else None)
                              for m, _ in METRICS},
                "winDiffPositiveCells": sum(1 for r in ok if r["winDiff"] > 0),
                "winDiffNegativeCells": sum(1 for r in ok if r["winDiff"] < 0),
                "file": "analysis/kensho06/strataCourseRank.csv"}
    s["stage3"] = {
        "definition": "線形確率モデル（1着・3着内）／線形モデル（平均着）を、切片・地元・場(24)・級別(4)・進入コース(1〜6＋不明)・"
                      "年齢帯(〜29/30〜39/40〜49/50〜)・出走数帯（選手×年の延べ走数の四分位）のダミーで全行に当てた。"
                      "各項目の寄与＝(地元の平均 − 非地元の平均)×係数 の和。残り＝地元ダミーの係数。"
                      "寄与の合計＋残り＝統制なしの差（closureError はその誤差）。符号の安定は年ごとに同じ分解をして見る",
        "startsQuartileCuts": [float(x) for x in q],
        "decomposition": res,
        "byYear": byYear,
        "signUnstable": unstable,
        "strata": cellInfo,
    }
    save_summary(s)
    print(json.dumps({k2: s["stage3"][k2] for k2 in ["startsQuartileCuts", "decomposition", "signUnstable", "strata"]},
                     ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- stage4

def stage4(work):
    D = load(work)
    s = load_summary()
    order = np.lexsort((D["dnum"], D["toban"]))
    tb, br, dn = D["toban"][order], D["bidx"][order], D["dnum"][order]
    home = D["home"][order]
    fin = D["fin"][order].astype(np.float64)
    course = D["course"][order].astype(np.int64)
    win, top3 = (fin == 1).astype(np.float64), (fin <= 3).astype(np.float64)
    cAll = D["course"].astype(np.int64)
    fAll = D["fin"].astype(np.float64)
    cnt = np.bincount(cAll, minlength=7)
    eWin = np.bincount(cAll, weights=(fAll == 1), minlength=7) / np.maximum(cnt, 1)
    eTop3 = np.bincount(cAll, weights=(fAll <= 3), minlength=7) / np.maximum(cnt, 1)
    eFin = np.bincount(cAll, weights=fAll, minlength=7) / np.maximum(cnt, 1)
    new = np.ones(len(tb), dtype=bool)
    new[1:] = (tb[1:] != tb[:-1]) | (br[1:] != br[:-1])
    sid = np.cumsum(new) - 1
    ns = int(sid[-1] + 1)

    def bc(w, mask):
        return np.bincount(sid[mask], weights=w[mask], minlength=ns)

    one = np.ones(len(tb))
    agg = {}
    for side, mk in (("H", home), ("N", ~home)):
        agg["n" + side] = bc(one, mk)
        agg["win" + side] = bc(win, mk)
        agg["top3" + side] = bc(top3, mk)
        agg["fin" + side] = bc(fin, mk)
        agg["eWin" + side] = bc(eWin[course], mk)
        agg["eTop3" + side] = bc(eTop3[course], mk)
        agg["eFin" + side] = bc(eFin[course], mk)
    first = np.flatnonzero(new)
    last = np.r_[first[1:] - 1, len(tb) - 1]
    stTob, stBr = tb[first], br[first]
    stintNo = np.zeros(ns, dtype=np.int64)
    for i in range(1, ns):
        stintNo[i] = stintNo[i - 1] + 1 if stTob[i] == stTob[i - 1] else 0
    elig = (agg["nH"] >= 20) & (agg["nN"] >= 20)
    with np.errstate(divide="ignore", invalid="ignore"):
        d = {
            "winDiff": agg["winH"] / agg["nH"] - agg["winN"] / agg["nN"],
            "winDiffCourseAdj": (agg["winH"] - agg["eWinH"]) / agg["nH"] - (agg["winN"] - agg["eWinN"]) / agg["nN"],
            "top3Diff": agg["top3H"] / agg["nH"] - agg["top3N"] / agg["nN"],
            "top3DiffCourseAdj": (agg["top3H"] - agg["eTop3H"]) / agg["nH"] - (agg["top3N"] - agg["eTop3N"]) / agg["nN"],
            "meanFinishDiff": agg["finH"] / agg["nH"] - agg["finN"] / agg["nN"],
            "meanFinishDiffCourseAdj": (agg["finH"] - agg["eFinH"]) / agg["nH"] - (agg["finN"] - agg["eFinN"]) / agg["nN"],
        }
    with open(os.path.join(OUTDIR, "withinRacer.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["toban", "stint", "branch", "firstDate", "lastDate", "nHome", "nNon",
                    "winsHome", "winsNon", "top3Home", "top3Non", "eligible"] + list(d.keys()))
        for i in range(ns):
            w.writerow([int(stTob[i]), int(stintNo[i]), BRANCH18[stBr[i]], ymd(dn[first[i]]), ymd(dn[last[i]]),
                        int(agg["nH"][i]), int(agg["nN"][i]), int(agg["winH"][i]), int(agg["winN"][i]),
                        int(agg["top3H"][i]), int(agg["top3N"][i]), int(elig[i])] +
                       [("%.6f" % d[k2][i]) if elig[i] else "" for k2 in d])

    def summ(x):
        x = x[elig]
        return {"median": round(float(np.median(x)), 6), "q1": round(float(np.quantile(x, 0.25)), 6),
                "q3": round(float(np.quantile(x, 0.75)), 6), "positive": int((x > 0).sum()),
                "negative": int((x < 0).sum()), "zero": int((x == 0).sum())}

    nb = collections.defaultdict(set)
    for t, b in zip(stTob.tolist(), stBr.tolist()):
        nb[t].add(b)
    transfer = sum(1 for v in nb.values() if len(v) > 1)
    stints_per = collections.Counter(stTob.tolist())
    returned = sum(1 for t, v in nb.items() if stints_per[t] > len(v))
    s["stage4"] = {
        "definition": "選手×支部の連続区間（支部が変わったら別人）を1単位。地元・非地元の両方に20走以上ある単位だけを対象。"
                      "差＝地元での値−非地元での値（平均着は小さいほど良い）。コース統制版は、各走から期待値"
                      "（全行の進入コース別の1着率・3着内率・平均着）を引いた残差の平均の差",
        "units": ns, "racers": len(nb), "eligibleUnits": int(elig.sum()), "excludedUnits": int((~elig).sum()),
        "eligibleRacers": len(set(stTob[elig].tolist())),
        "transferRacers": transfer, "racersReturningToEarlierBranch": returned,
        "raw": {k2: summ(d[k2]) for k2 in ("winDiff", "top3Diff", "meanFinishDiff")},
        "courseAdjusted": {k2: summ(d[k2]) for k2 in ("winDiffCourseAdj", "top3DiffCourseAdj", "meanFinishDiffCourseAdj")},
        "note": "単位ごとの差は n=20 からで、単位ごとの率は n<300。集計（中央値・四分位・符号の人数）だけを結果として使う",
        "file": "analysis/kensho06/withinRacer.csv",
    }
    save_summary(s)
    print(json.dumps(s["stage4"], ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- stage5

def required_n(h, p0):
    p1 = p0 + DELTA
    pbar = h * p1 + (1 - h) * p0
    a = Z * math.sqrt(pbar * (1 - pbar) * (1 / h + 1 / (1 - h)))
    b = Z_BETA * math.sqrt(p1 * (1 - p1) / h + p0 * (1 - p0) / (1 - h))
    return (a + b) ** 2 / DELTA ** 2


def power_layers(D):
    home, win = D["home"], D["fin"] == 1
    layers = [("全体", "全体", np.ones(len(home), dtype=bool))]
    for j in sorted(VENUE_BRANCH):
        layers.append(("場", j + " " + VENUE_BRANCH[j][0], D["jcd"] == int(j)))
    for i, b in enumerate(BRANCH18):
        layers.append(("支部", b, D["bidx"] == i))
    for k, rk in enumerate(RANKS):
        for c in range(1, 7):
            layers.append(("級別×進入", "%s×%dコース" % (rk, c), (D["rank"] == k) & (D["course"] == c)))
    for y in YEARS:
        layers.append(("年", str(y), D["year"] == y))
    out = []
    for kind, key, m in layers:
        nT = int(m.sum())
        nH = int((m & home).sum())
        nN = nT - nH
        row = {"layer": kind, "key": key, "nTotal": nT, "nHome": nH, "nNon": nN}
        if nH == 0 or nN == 0:
            row.update({"homeShare": round(nH / nT, 6) if nT else "", "p0NonHomeWin": "",
                        "requiredN": "", "sufficiency": "", "note": "地元または非地元が0で算出不可"})
        else:
            h = nH / nT
            p0 = float(win[m & ~home].mean())
            req = required_n(h, p0)
            row.update({"homeShare": round(h, 6), "p0NonHomeWin": round(p0, 6), "requiredN": int(math.ceil(req)),
                        "sufficiency": round(nT / req, 4), "note": "" if nT >= req else "充足率1.0未満"})
        out.append(row)
    return out


def stage5(work):
    D = load(work)
    s = load_summary()
    rows = power_layers(D)
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "power.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    under = [r["layer"] + ":" + r["key"] for r in rows if r["note"]]
    s["stage5"] = {
        "definition": "α=0.05（両側）・検出力0.8。1着率で非地元 p0（その層の実測）に対し地元が p0+0.02 のとき、"
                      "地元比率 h（その層の実測）のもとで、2標本の比率の差を検出するのに要る延べ走数（地元＋非地元）。"
                      "充足率＝実際n/必要n",
        "alpha": 0.05, "power": 0.8, "delta": DELTA,
        "overall": rows[0],
        "underpoweredLayers": under,
        "counts": {k2: {"layers": sum(1 for r in rows if r["layer"] == k2),
                        "sufficient": sum(1 for r in rows if r["layer"] == k2 and not r["note"])}
                   for k2 in ["全体", "場", "支部", "級別×進入", "年"]},
        "file": "analysis/kensho06/power.csv",
    }
    save_summary(s)
    print(json.dumps(s["stage5"], ensure_ascii=False, indent=1))
    if rows[0]["note"]:
        stop(s, "stage5 の充足率が全体で1.0を下回った")


# ---------------------------------------------------------------- stage6

def stage6(work):
    D = load(work)
    s = load_summary()
    rd, vd = district_of(D)
    home = D["home"]
    near = (~home) & (rd == vd)
    far = (~home) & (rd != vd)
    t1, t2, t3 = rates(D, home), rates(D, near), rates(D, far)
    d12, d23 = diff3(t1, t2), diff3(t2, t3)
    judge = {}
    for m, _ in METRICS:
        if d12[m] is None or d23[m] is None:
            judge[m] = "n不足で判定しない"
        else:
            judge[m] = ("2と3の差が1と2の差より大きい（「地元」という切り方自体が間違っている）"
                        if abs(d23[m]) > abs(d12[m]) else "1と2の差が2と3の差以上")
    s["stage6"] = {
        "definition": "1 完全地元＝支部が開催場の所在地支部（裁定1）と一致 / 2 近接＝一致しないが同じ地区 / 3 遠隔＝それ以外。"
                      "地区はスクリプトの6地区（支部→地区の対応は districtTable）",
        "districtTable": {dname: [b for b in BRANCH18 if DISTRICT[b] == dname]
                          for dname in ["関東", "東海", "近畿", "四国", "中国", "九州"]},
        "tier1Home": t1, "tier2Near": t2, "tier3Far": t3,
        "diff1minus2": d12, "diff2minus3": d23, "judgement": judge,
    }
    save_summary(s)
    print(json.dumps(s["stage6"], ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- stage7

def stage7(work):
    D = load(work)
    s = load_summary()
    nz = np.load(os.path.join(work, "null.npz"))
    power = {(r["layer"], r["key"]): r for r in power_layers(D)}
    home = D["home"]
    win = D["fin"] == 1

    def block(mask, nullsum, pkey):
        nT = int(mask.sum())
        nH = int((mask & home).sum())
        H, N = rates(D, mask & home), rates(D, mask & ~home)
        row = {"nHome": nH, "nNon": nT - nH, "homeShare": round(nH / nT, 6) if nT else None,
               "home": H, "nonHome": N, "rawDiff": diff3(H, N)}
        pw = power[pkey]
        row["sufficiency"] = pw["sufficiency"]
        row["underpowered"] = bool(pw["note"])
        if nH >= NMIN and nT - nH >= NMIN:
            obs = win[mask & home].sum() / nH - win[mask & ~home].sum() / (nT - nH)
            null = sums_to_diff(nullsum, float(win[mask].sum()), nH, nT)
            row["winWithinRaceNull"] = nullstat(obs, null)
        else:
            row["winWithinRaceNull"] = "n不足"
        return row

    years = {}
    for i, y in enumerate(YEARS):
        years[str(y)] = block(D["year"] == y, nz["year"][:, 0, i], ("年", str(y)))
    venues = {}
    for i, j in enumerate(sorted(VENUE_BRANCH)):
        key = j + " " + VENUE_BRANCH[j][0]
        venues[key] = block(D["jcd"] == int(j), nz["venue"][:, 0, i], ("場", key))
    suffY = [y for y, r in years.items() if not r["underpowered"] and isinstance(r["winWithinRaceNull"], dict)]
    ex = [years[y]["winWithinRaceNull"]["excess"] for y in suffY]
    steps = np.sign(np.diff(ex)) if len(ex) > 1 else np.array([])
    shape = {"sufficientYears": suffY,
             "excessSufficientYears": dict(zip(suffY, ex)),
             "monotonic": bool(len(steps) > 0 and (np.all(steps > 0) or np.all(steps < 0))),
             "yearsNotSufficient": [y for y in years if y not in suffY]}
    suffV = [v for v, r in venues.items() if not r["underpowered"] and isinstance(r["winWithinRaceNull"], dict)]
    s["stage7"] = {
        "definition": "年・場ごとに、統制なしの差（rawDiff）と、stage2 のレース内シャッフル帰無（同じ1000回を年・場で集計）に対する"
                      "1着率差の超過（excess＝観測−帰無平均）。順位・大小は stage5 の充足率1.0以上の層だけ",
        "byYear": years, "yearShape": shape,
        "homeShareByYear": {y: r["homeShare"] for y, r in years.items()},
        "byVenue": venues,
        "venueSufficient": suffV,
        "venueRankByWinExcess_sufficientOnly": sorted(suffV, key=lambda v: -venues[v]["winWithinRaceNull"]["excess"]),
        "venueHomeShareRank_sufficientOnly": sorted(suffV, key=lambda v: -venues[v]["homeShare"]),
    }
    save_summary(s)
    print(json.dumps({k2: s["stage7"][k2] for k2 in ["yearShape", "homeShareByYear", "venueSufficient",
                                                      "venueRankByWinExcess_sufficientOnly",
                                                      "venueHomeShareRank_sufficientOnly"]},
                     ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- stage8

def stage8(work):
    s = load_summary()
    floor = round(1 / (NREP + 1), 6)
    ps = [("stage2:" + m, v["p"]) for m, v in s["stage2"]["stats"].items()]
    for grp in ("byYear", "byVenue"):
        for k2, r in s["stage7"][grp].items():
            if isinstance(r["winWithinRaceNull"], dict):
                ps.append(("stage7:%s:%s" % (grp, k2), r["winWithinRaceNull"]["p"]))
    atFloor = [k2 for k2, p in ps if p <= floor + 1e-9]
    nshort = []
    with open(os.path.join(OUTDIR, "strataCourseRank.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["note"]:
                nshort.append("strataCourseRank.csv: %sコース×%s" % (r["course"], r["rank"]))
    for grp in ("byYear", "byVenue"):
        for k2, r in s["stage7"][grp].items():
            if r["winWithinRaceNull"] == "n不足":
                nshort.append("summary.json stage7.%s.%s" % (grp, k2))
    s["stage8"] = {
        "pAtShuffleFloor": {"floor": floor, "count": len(atFloor), "items": atFloor,
                            "note": "下限で同値の p どうしには順位の意味がない"},
        "nShortCells": {"count": len(nshort), "items": nshort,
                        "note": "withinRacer.csv の単位ごとの差は n=20〜 で、単独の率としては使わない"},
        "decompositionSignUnstable": s["stage3"]["signUnstable"],
        "branchUnreadableRows": {"count": s["stage0"]["branchOther"]["rows"],
                                 "handling": "18種以外は率に混ぜず件数だけ報告する"},
        "notMeasured": [
            "出身地との違い（データに出身地が無い。支部は登録上の所属）",
            "移籍の理由（B に出るのは支部表記の変化だけ）",
            "ホームアドバンテージの機序（水面の慣れ・移動の負担・応援など、区別できない）",
            "地元戦に誰が呼ばれるかという選ばれ方（斡旋の決まり方がデータに無い）",
            "モーター・ボートの当たり（今回の統制に入れていない）",
            "2016年（11〜12月のみ）と2026年（〜8月11日）は部分年で、出走数帯や年別の値が他の年と同じ条件ではない",
        ],
    }
    s["meta"]["stagesFinishedJST"] = jst_now()
    save_summary(s)
    print(json.dumps(s["stage8"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    cmd, work = sys.argv[1], sys.argv[2]
    {"extract": extract, "stage0": stage0, "stage1": stage1, "stage2": stage2, "stage3": stage3,
     "stage4": stage4, "stage5": stage5, "stage6": stage6, "stage7": stage7, "stage8": stage8}[cmd](work)


