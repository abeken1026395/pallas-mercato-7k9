#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""展示タイム別の成績（選手別）を作る。

正本 : data/tenjiStats/state.json   回数の累積（選手 x 区分 x 進入コース）と全体セル
入力 : --kfiles DIR [--until YYYYMMDD]  Kファイル（kYYMMDD.lzh）から正本を作り直す（ローカル専用）
       引数なし       preview/YYYYMMDD.json と results/YYYYMMDD.json から、
                      正本の to より新しく、前日（JST）以前の日だけ足す
出力 : docs/data/tenjiStats.json    直近365日に走った選手のみ。回数と同コース期待値（率は表示側で計算）

区分 : g = 単独トップで2位と0.03秒以上の差 / b = そのレースの平均より0.03秒以上遅い / n = それ以外
       タイムは100倍した整数で比べる。展示タイムのある艇が5艇以上のレースだけ数える
着   : 1から6着はそのまま。F・L・失格（results の着7から15）は着外として分母に含める
       欠場（results の着16・Kファイルの展示なし行）は数えない。1着の艇がいないレースは除く
       進入コースのない着外艇（出遅れ等。Kファイルでは進入が空欄）は平均にも回数にも入れない
"""
import argparse
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "tenjiStats", "state.json")
OUT = os.path.join(ROOT, "docs", "data", "tenjiStats.json")
PREVIEW = os.path.join(ROOT, "preview")
RESULTS = os.path.join(ROOT, "results")
KINDS = "gnb"
ACTIVE_DAYS = 365
DQ_K = {"F", "L0", "L1", "S0", "S1", "S2"}

# LZH解凍は buildMotorUsage.py と同じ順（lhafile → Windows同梱 bsdtar）。
# lhafile は Python3.14 で C拡張のビルドが通らないため、Windows では bsdtar が本命
BSDTAR = os.environ.get(
    "BSDTAR", os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe"))

K_ENTRY = re.compile(r"^\s+(\S\S?)\s+(\d)\s+(\d{4})\s(.+?)\s(\d+)\s+(\d+)\s+(\d\.\d\d)\s+(\d)\s")
K_RACE = re.compile(r"^\s+(\d+)R\s")


def new_state():
    return {"meta": {"from": "", "to": ""}, "cell": {}, "r": {}}


def add_race(st, hd, boats):
    """boats: [(toban, course, tenji100, pos)]。pos は 1..6、着外は 9。"""
    if len(boats) < 5 or not any(b[3] == 1 for b in boats):
        return 0
    n = len(boats)
    tot = sum(b[2] for b in boats)
    ts = sorted(b[2] for b in boats)
    for toban, c, t, pos in boats:
        if t == ts[0] and ts[1] - t >= 3:
            k = "g"
        elif t * n - tot >= 3 * n:
            k = "b"
        else:
            k = "n"
        hit = [1, 1 if pos == 1 else 0, 1 if pos <= 2 else 0, 1 if pos <= 3 else 0]
        cell = st["cell"].setdefault("%d%s" % (c, k), [0, 0, 0, 0])
        r = st["r"].setdefault(str(toban), {"s": hd, "last": hd, "g": [[0] * 4 for _ in range(6)],
                                            "n": [[0] * 4 for _ in range(6)], "b": [[0] * 4 for _ in range(6)]})
        if hd < r["s"]:
            r["s"] = hd
        if hd > r["last"]:
            r["last"] = hd
        slot = r[k][c - 1]
        for j in range(4):
            cell[j] += hit[j]
            slot[j] += hit[j]
    return 1


def k_races(text, hd):
    jcd = None
    rno = None
    races = {}
    for line in text.splitlines():
        if line.endswith("KBGN"):
            jcd = line[:2]
            rno = None
            continue
        m = K_RACE.match(line)
        if m and ("H1" in line or "m " in line):
            rno = int(m.group(1))
            continue
        m = K_ENTRY.match(line)
        if m and jcd and rno:
            races.setdefault((jcd, rno), []).append(m.groups())
    out = []
    for key in sorted(races):
        rows = races[key]
        if any(g[0] == "00" for g in rows):
            continue
        boats = []
        for g in rows:
            code = g[0]
            if code.isdigit() and 1 <= int(code) <= 6:
                pos = int(code)
            elif code in DQ_K:
                pos = 9
            else:
                continue
            boats.append((int(g[2]), int(g[7]), int(round(float(g[6]) * 100)), pos))
        out.append(boats)
    return out


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


def build_from_kfiles(kdir, until):
    st = new_state()
    files = sorted(glob.glob(os.path.join(kdir, "k*.lzh")))
    if until:
        files = [fn for fn in files if "20" + os.path.basename(fn)[1:7] <= until]
    if not files:
        print("ERROR: no kfiles in %s" % kdir, file=sys.stderr)
        sys.exit(1)
    nr = 0
    for fn in files:
        hd = "20" + os.path.basename(fn)[1:7]
        text = unlzh(fn).decode("cp932", errors="replace")
        for boats in k_races(text, hd):
            nr += add_race(st, hd, boats)
        st["meta"]["to"] = hd
        if not st["meta"]["from"]:
            st["meta"]["from"] = hd
    return st, nr, len(files)


def json_races(pv_path, rs_path):
    with io.open(pv_path, "r", encoding="utf-8") as f:
        pv = json.load(f).get("直前情報", []) or []
    with io.open(rs_path, "r", encoding="utf-8") as f:
        rs = json.load(f).get("結果", []) or []
    tj = {}
    for p in pv:
        key = (int(p.get("stadium_number") or 0), int(p.get("race_number") or 0))
        tj[key] = {int(b.get("entry_number") or 0): b.get("exhibition_time") for b in (p.get("racers") or [])}
    out = []
    for r in rs:
        try:
            key = (int(r.get("場コード")), int(str(r.get("レース")).rstrip("R")))
        except (TypeError, ValueError):
            continue
        ex = tj.get(key)
        if not ex:
            continue
        boats = []
        broken = False
        for b in r.get("艇") or []:
            ch = b.get("着")
            if not isinstance(ch, int) or ch == 16 or ch < 1:
                continue
            pos = ch if ch <= 6 else 9
            c = b.get("コース")
            t = ex.get(int(b.get("枠") or 0))
            if not isinstance(t, (int, float)) or t <= 0:
                broken = True
                break
            if not isinstance(c, int) or not 1 <= c <= 6:
                if pos != 9:
                    broken = True
                    break
                continue
            boats.append((int(b.get("登番")), c, int(round(t * 100)), pos))
        if not broken:
            out.append(boats)
    return out


def update_from_json(st):
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")
    to = st["meta"]["to"]
    days = 0
    nr = 0
    for rs_path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        hd = os.path.basename(rs_path)[:8]
        if not (hd.isdigit() and len(hd) == 8) or hd <= to or hd >= today:
            continue
        pv_path = os.path.join(PREVIEW, hd + ".json")
        if not os.path.exists(pv_path):
            break
        for boats in json_races(pv_path, rs_path):
            nr += add_race(st, hd, boats)
        st["meta"]["to"] = hd
        if not st["meta"]["from"]:
            st["meta"]["from"] = hd
        days += 1
    return nr, days


def build_out(st):
    rate = {}
    for key, v in st["cell"].items():
        rate[key] = [v[j] / v[0] for j in (1, 2, 3)] if v[0] else [0.0, 0.0, 0.0]
    avg = {}
    for k in KINDS:
        tot = [sum(st["cell"].get("%d%s" % (c, k), [0, 0, 0, 0])[j] for c in range(1, 7)) for j in range(4)]
        avg[k] = [round(tot[j] / tot[0] * 100, 1) if tot[0] else 0.0 for j in (1, 2, 3)]
    lo = (datetime.strptime(st["meta"]["to"], "%Y%m%d") - timedelta(days=ACTIVE_DAYS - 1)).strftime("%Y%m%d")
    racers = {}
    for toban in sorted(st["r"], key=int):
        r = st["r"][toban]
        if r["last"] < lo:
            continue
        o = {"s": r["s"][:6]}
        for k in KINDS:
            cnt = [sum(r[k][c][j] for c in range(6)) for j in range(4)]
            exp = [round(sum(r[k][c][0] * rate.get("%d%s" % (c + 1, k), [0.0, 0.0, 0.0])[j] for c in range(6)), 1)
                   for j in range(3)]
            o[k] = cnt + exp
        racers[toban] = o
    return {"meta": {"from": st["meta"]["from"], "to": st["meta"]["to"], "racers": len(racers), "avg": avg},
            "r": racers}


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
        f.write("\n")
    return len(s.encode("utf-8")) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kfiles", help="Kファイルのフォルダ。指定すると正本を作り直す")
    ap.add_argument("--until", help="--kfiles で読む最終日 YYYYMMDD（省略時は全部）")
    a = ap.parse_args()
    if a.kfiles:
        st, nr, nf = build_from_kfiles(a.kfiles, a.until)
        print("KFILES=%d RACES=%d" % (nf, nr))
    else:
        if not os.path.exists(STATE):
            print("ERROR: %s がない。先に --kfiles で作る" % STATE, file=sys.stderr)
            sys.exit(1)
        with io.open(STATE, "r", encoding="utf-8") as f:
            st = json.load(f)
        nr, days = update_from_json(st)
        print("DAYS_ADDED=%d RACES_ADDED=%d" % (days, nr))
    sb = write_json(STATE, st)
    out = build_out(st)
    ob = write_json(OUT, out)
    print("FROM=%s TO=%s RACERS=%d STATE_BYTES=%d OUT_BYTES=%d" % (
        out["meta"]["from"], out["meta"]["to"], out["meta"]["racers"], sb, ob))


if __name__ == "__main__":
    main()
