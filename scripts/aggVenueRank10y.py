# -*- coding: utf-8 -*-
"""aggVenueRank10y.py — 24場を数字で並べる（Kファイル版の集計）

出力の形は実験場の試作（results 版）と同じにし、区切りを「年」にする。風向きと強さ別を加える。

使い方
  py scripts/aggVenueRank10y.py lzh  <Kファイルのフォルダ> <出力JSON> [開始YYYYMMDD] [終了YYYYMMDD]
  py scripts/aggVenueRank10y.py csv  <kdata のフォルダ>     <出力JSON>     ← 試験用（kdata の CSV を読む）

入力
  Kファイル kYYMMDD.lzh（読むだけ）。解凍は buildKensho07Stage1.decode_kfile、解析は kparser.parse_day
  級別 docs/data/rankHistory.json（Bファイル由来。その日以前の最後の記録を使う）
  水面方位 docs/data/stadiumBearing.json

決まりごと
  欠場（着が K で始まる）は除き、進入コースが 1〜6 で取れた艇だけを数える。残りが5艇未満のレースは除く
  1着は着 "01" / "1"。3連単の払戻は払戻の「３連単」の1件目
  風向き：Kファイルの方位は場ごとに一定の角度だけ回った向きで書かれている（2025-07〜2026-07 の
  results の風向コードと全場100%で一致する回転。WIND_OFFSET）。回したあと /results/ と同じ決まりで
  追い風（水面の向きとの差45度以下）・向かい風（135度以上）・横風に分ける。2m以下と無風は「弱」
結論は書かない。数えるだけ。
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

VENUES = ["%02d" % i for i in range(1, 25)]
GRADES = ("A1", "A2", "B1", "B2")
WIND_BINS = ("弱", "追い3-4m", "追い5m以上", "向かい3-4m", "向かい5m以上", "横3-4m", "横5m以上")
ANG = {"北": 0, "北東": 45, "東": 90, "南東": 135, "南": 180, "南西": 225, "西": 270, "北西": 315}
# Kファイルの方位に足すと results の風向コードの角度（吹いていく方位）になる角度。2025-07-22〜2026-07-21 で全場100%一致
WIND_OFFSET = {"01": 112.5, "02": 157.5, "03": 247.5, "04": 270.0, "05": 0.0, "06": 90.0, "07": 45.0, "08": 0.0,
               "09": 337.5, "10": 112.5, "11": 90.0, "12": 90.0, "13": 22.5, "14": 135.0, "15": 315.0, "16": 90.0,
               "17": 45.0, "18": 315.0, "19": 45.0, "20": 22.5, "21": 180.0, "22": 202.5, "23": 67.5, "24": 225.0}


def load_rank():
    d = json.load(open(os.path.join(ROOT, "docs", "data", "rankHistory.json"), encoding="utf-8"))
    return {int(k): v for k, v in d["選手"].items()}


def grade_of(rank, toban, ymd):
    """ymd は YYYY-MM-DD。その日以前の最後の記録"""
    h = rank.get(toban)
    if not h:
        return None
    g = None
    for d, x in h:
        if d <= ymd:
            g = x
        else:
            break
    return g


def bearing():
    d = json.load(open(os.path.join(ROOT, "docs", "data", "stadiumBearing.json"), encoding="utf-8"))
    return {k: v["方位"] for k, v in d["場"].items()}


def num(s, suffix):
    s = (s or "").strip()
    if s.endswith(suffix):
        s = s[: -len(suffix)]
    try:
        return int(s)
    except ValueError:
        return None


class Agg:
    def __init__(self):
        self.rate = defaultdict(lambda: [0, 0])
        self.mean = defaultdict(lambda: [0.0, 0, 0.0])
        self.grade = defaultdict(lambda: [0, 0])
        self.seas = defaultdict(lambda: [0, 0])
        self.wind = defaultdict(lambda: [0, 0])
        self.days = set()
        self.windUnknown = 0
        self.rank = load_rank()
        self.bear = bearing()

    def race(self, ymd8, jcd, rinfo, ents, tri):
        if jcd not in VENUES:
            return
        boats = []
        for e in ents:
            ch = (e.get("chaku") or "").strip()
            if ch.startswith("K"):
                continue
            try:
                c = int(e.get("shinnyu") or "")
                w = int(e.get("waku") or "")
            except ValueError:
                continue
            if 1 <= c <= 6:
                boats.append((c, w, ch, e.get("toban")))
        if len(boats) < 5:
            return
        self.days.add(ymd8)
        y = ymd8[:4]
        m = int(ymd8[4:6])
        ymd = "%s-%s-%s" % (ymd8[:4], ymd8[4:6], ymd8[6:])
        s = "冬" if m in (12, 1, 2) else "夏" if m in (6, 7, 8) else None

        def addr(k, x):
            for q in ("ALL", y):
                c = self.rate[(k, jcd, q)]; c[0] += x; c[1] += 1

        def addm(k, x):
            for q in ("ALL", y):
                c = self.mean[(k, jcd, q)]; c[0] += x; c[1] += 1; c[2] += x * x

        ws = num(rinfo.get("windMps"), "m")
        wd = (rinfo.get("windDir") or "").strip()
        wbin = None
        if ws is not None:
            if ws <= 2 or wd == "無風":
                wbin = "弱"
            elif wd in ANG:
                a = (ANG[wd] + WIND_OFFSET[jcd]) % 360
                diff = abs((a - self.bear[jcd] + 180) % 360 - 180)
                side = "追い" if diff <= 45 else "向かい" if diff >= 135 else "横"
                wbin = side + ("5m以上" if ws >= 5 else "3-4m")
            else:
                self.windUnknown += 1

        for c, w, ch, toban in boats:
            win = 1 if ch in ("01", "1") else 0
            if c == 1:
                addr("c1", win)
                if s:
                    self.seas[(jcd, s)][0] += win; self.seas[(jcd, s)][1] += 1
                try:
                    g = grade_of(self.rank, int(toban), ymd)
                except (TypeError, ValueError):
                    g = None
                if g in GRADES:
                    self.grade[(jcd, g)][0] += win; self.grade[(jcd, g)][1] += 1
                if wbin:
                    self.wind[(jcd, wbin)][0] += win; self.wind[(jcd, wbin)][1] += 1
            if c == 4:
                addr("c4", win)
        if tri is not None and tri > 0:
            addr("man", 1 if tri >= 10000 else 0)
        order = [w for c, w, _, _ in sorted(boats)]
        addr("shin", 0 if order == sorted(order) else 1)
        if ws is not None:
            addm("wind", ws)
        wv = num(rinfo.get("waveCm"), "cm")
        if wv is not None:
            addm("wave", wv)

    def dump(self, out, source):
        days = sorted(self.days)
        years = sorted({d[:4] for d in days})
        o = {
            "出典": source,
            "期間": [days[0], days[-1]],
            "区切り": "年",
            "区切り一覧": years,
            "レース数": sum(self.rate[("shin", v, "ALL")][1] for v in VENUES),
            "定義": "欠場を除き進入コースが取れた艇。5艇未満のレースは除く。級別は rankHistory.json のその日以前の最後の記録",
            "指標": {},
            "級別": {"期間": [days[0], days[-1]], "場": {}},
            "季節": {"冬の月": [12, 1, 2], "夏の月": [6, 7, 8], "場": {}},
            "風": {"区分": list(WIND_BINS), "定義": "1コースの1着率。弱＝2m以下か無風。追い風＝水面の向きとの差45度以下、向かい風＝135度以上、ほかは横風",
                  "方位不明": self.windUnknown, "場": {}},
        }
        for k in ("c1", "c4", "man", "shin"):
            o["指標"][k] = {"型": "率", "場": {v: self.rate[(k, v, "ALL")] for v in VENUES},
                           "区切り": {v: {q: self.rate[(k, v, q)] for q in years} for v in VENUES}}
        for k in ("wind", "wave"):
            o["指標"][k] = {"型": "平均", "場": {v: self.mean[(k, v, "ALL")] for v in VENUES},
                           "区切り": {v: {q: self.mean[(k, v, q)] for q in years} for v in VENUES}}
        for v in VENUES:
            o["級別"]["場"][v] = {g: self.grade[(v, g)] for g in GRADES}
            o["季節"]["場"][v] = {s: self.seas[(v, s)] for s in ("冬", "夏")}
            o["風"]["場"][v] = {b: self.wind[(v, b)] for b in WIND_BINS}
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(o, f, ensure_ascii=False, separators=(",", ":"))
        print("書き出し", out, "期間", o["期間"], "日数", len(days), "レース", o["レース数"], "方位不明", self.windUnknown)


def tri_of(pays):
    for p in pays:
        if p.get("shiki") == "３連単":
            try:
                return int(p.get("payout") or "")
            except ValueError:
                return None
    return None


def run_csv(folder, out):
    agg = Agg()
    races = {}
    for r in csv.DictReader(open(os.path.join(folder, "racesAll.csv"), encoding="utf-8")):
        races[(r["hd"], r["jcd"], r["rno"])] = r
    ents = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(folder, "entries2*.csv"))):
        for e in csv.DictReader(open(f, encoding="utf-8")):
            ents[(e["hd"], e["jcd"], e["rno"])].append(e)
    pays = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(folder, "payouts2*.csv"))):
        for p in csv.DictReader(open(f, encoding="utf-8")):
            pays[(p["hd"], p["jcd"], p["rno"])].append(p)
    for k in sorted(races):
        agg.race("20" + k[0], k[1], races[k], ents.get(k, []), tri_of(pays.get(k, [])))
    agg.dump(out, "kdata（Kファイル由来CSV）")


def run_lzh(folder, out, start, end):
    from kparser import parse_day
    from buildKensho07Stage1 import decode_kfile, file_hd
    agg = Agg()
    files = sorted(glob.glob(os.path.join(folder, "*.lzh")))
    nfile = 0
    for path in files:
        ymd8 = file_hd(path)
        if not ymd8 or ymd8 < start or ymd8 > end:
            continue
        nfile += 1
        d = parse_day(decode_kfile(path), ymd8[2:])
        ents = defaultdict(list)
        for e in d["entries"]:
            ents[(e["jcd"], str(e["rno"]))].append(e)
        pays = defaultdict(list)
        for p in d["payouts"]:
            pays[(p["jcd"], str(p["rno"]))].append(p)
        for r in d["races"]:
            k = (r["jcd"], str(r["rno"]))
            agg.race(ymd8, r["jcd"], r, ents.get(k, []), tri_of(pays.get(k, [])))
    print("読んだファイル", nfile)
    agg.dump(out, "Kファイル（BOAT RACE 公式の競走成績）")


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    mode, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if mode == "csv":
        run_csv(src, out)
    elif mode == "lzh":
        start = sys.argv[4] if len(sys.argv) > 4 else "20161101"
        end = sys.argv[5] if len(sys.argv) > 5 else "29991231"
        run_lzh(src, out, start, end)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
