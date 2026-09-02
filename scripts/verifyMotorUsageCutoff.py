#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motorUsage の残差が「終端日のズレ」で説明できるかを見る検証スクリプト。

docs には何も書かない。標準出力だけ。

やること:
  1. Kアーカイブを buildMotorUsage と同じ手順で読む
  2. 各場の coverageFrom は docs/data/motorUsage.json の推定値で固定する
     （開始日は動かさない＝終端だけの効果を見る）
  3. 終端日 D を振りながら [coverageFrom, D] で2連率を数え直し、
     教師との平均絶対誤差が最小になる D を場ごとに出す
  4. 教師は2種類で比較する
       teacherAll   = docs/motor/motors_all.csv（場ごと最終開催日の公式値）
       teacherToday = docs/racers/racers_today.csv（本日出走表の公式値）
"""
import csv
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildMotorUsage as B

USAGE = os.path.join("docs", "data", "motorUsage.json")
TODAY_CSV = os.path.join("docs", "racers", "racers_today.csv")
TAIL_DAYS = 12  # 終端の候補としてさかのぼる開催日数


def load_today_teacher(path=TODAY_CSV):
    """出走表CSV → {jcd: {機番: 公式2連対率}}。"""
    if not os.path.exists(path):
        print("  [warn] 出走表CSVが無い: {}".format(path))
        return {}
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            jcd = str(row.get("場コード") or "").strip().zfill(2)
            mno = B.mkey(row.get("モーターNo"))
            try:
                rate = float(row.get("モーター2連率"))
            except (TypeError, ValueError):
                continue
            if not jcd or not mno:
                continue
            out.setdefault(jcd, {})[mno] = rate
    return out


def teacher_days(path=B.TEACHER):
    """motors_all.csv の場ごと最終開催日 {jcd: YYYYMMDD}。"""
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            jcd = str(row.get("場コード") or "").strip().zfill(2)
            hd = str(row.get("開催日") or "").strip()
            if jcd and hd and hd > out.get(jcd, ""):
                out[jcd] = hd
    return out


def read_records():
    """buildMotorUsage と同じ手順で明細 [(開催日, jcd, 機番, 着順)] を作る。"""
    files = []
    for root, _dirs, names in os.walk(B.KFILES_DIR):
        for n in names:
            files.append(os.path.join(root, n))
    files.sort()
    records = []
    for p in files:
        try:
            text = B.decode_kfile(p)
        except Exception:
            continue
        if not text:
            continue
        hd = B.file_date(text, p)
        if not hd:
            continue
        for (jcd, chaku, _lane, _toban, _name, mno, _bno) in B.parse_text(text):
            records.append((hd, jcd, B.mkey(mno), chaku))
    print("Kアーカイブ {}ファイル / 明細{}件".format(len(files), len(records)))
    return records


def by_venue_day(records):
    bv = {}
    for (hd, jcd, mno, chaku) in records:
        day = bv.setdefault(jcd, {}).setdefault(hd, {})
        a = day.get(mno)
        if a is None:
            a = day[mno] = [0, 0, 0, 0]
        a[0] += 1
        n = int(chaku) if str(chaku).isdigit() else 0
        if n == 1:
            a[1] += 1
        if 1 <= n <= 2:
            a[2] += 1
        if 1 <= n <= 3:
            a[3] += 1
    return bv


def err_at(by_day, start, end, teacher_v):
    """[start, end] で数え直した2連率と教師の平均絶対誤差。(誤差, 照合機数)。"""
    cum = {}
    for hd in by_day:
        if hd < start or hd > end:
            continue
        for mno, c in by_day[hd].items():
            a = cum.get(mno)
            if a is None:
                a = cum[mno] = [0, 0, 0, 0]
            a[0] += c[0]; a[1] += c[1]; a[2] += c[2]; a[3] += c[3]
    tot = 0.0
    n = 0
    for mno, rate in teacher_v.items():
        a = cum.get(mno)
        if a is None or a[0] < B.MIN_RUNS:
            continue
        tot += abs(a[2] / a[0] * 100.0 - rate)
        n += 1
    if n < B.MIN_MATCHED:
        return None, n
    return tot / n, n


def run(label, teacher, bv, starts, tdays):
    print("")
    print("=== 教師: {} ===".format(label))
    print("{:<8}{:>10}{:>10}{:>9}{:>9}{:>8}{:>7}".format(
        "場", "最終日", "最良終端", "その誤差", "9/1誤差", "改善", "照合機"))
    gains = []
    for jcd in sorted(starts):
        tv = teacher.get(jcd, {})
        by_day = bv.get(jcd, {})
        if not tv or not by_day:
            continue
        start = starts[jcd]
        days = sorted([d for d in by_day if d >= start])
        if not days:
            continue
        cands = days[-TAIL_DAYS:]
        base_end = days[-1]

        # 照合対象を固定する。終端を切ると MIN_RUNS を割る機が抜けて
        # 平均誤差が下がるため、最短の終端でも MIN_RUNS を満たす機だけを使う。
        fixed = None
        for d in cands:
            cum = {}
            for hd in by_day:
                if hd < start or hd > d:
                    continue
                for mno, c in by_day[hd].items():
                    a = cum.get(mno)
                    if a is None:
                        a = cum[mno] = [0, 0, 0, 0]
                    a[0] += c[0]; a[1] += c[1]; a[2] += c[2]; a[3] += c[3]
            ok = set(m for m, a in cum.items() if m in tv and a[0] >= B.MIN_RUNS)
            fixed = ok if fixed is None else (fixed & ok)
        if not fixed or len(fixed) < B.MIN_MATCHED:
            print("{:<8}{:>10}  照合機{}機で判定不能（MIN_MATCHED未満）".format(
                B.VENUES.get(jcd, jcd), tdays.get(jcd, "-"), len(fixed or [])))
            continue
        tvf = {m: tv[m] for m in fixed}

        base, nb = err_at2(by_day, start, base_end, tvf)
        best = None
        for d in cands:
            e, n = err_at2(by_day, start, d, tvf)
            if e is None:
                continue
            if best is None or e < best[1]:
                best = (d, e, n)
        if best is None or base is None:
            continue
        gain = base - best[1]
        gains.append(gain)
        print("{:<8}{:>10}{:>10}{:>9.2f}{:>9.2f}{:>8.2f}{:>7}".format(
            B.VENUES.get(jcd, jcd), tdays.get(jcd, "-"), best[0],
            best[1], base, gain, len(tvf)))
    if gains:
        print("  改善の平均 {:+.2f}pt / 中央値 {:+.2f}pt / 改善した場 {}/{}".format(
            statistics.mean(gains), statistics.median(gains),
            sum(1 for g in gains if g > 0.01), len(gains)))


def err_at2(by_day, start, end, teacher_v):
    """err_at と同じだが MIN_RUNS / MIN_MATCHED の足切りをしない。
    照合対象は呼び出し側で固定済みなので、ここで母集団を動かしてはいけない。"""
    cum = {}
    for hd in by_day:
        if hd < start or hd > end:
            continue
        for mno, c in by_day[hd].items():
            a = cum.get(mno)
            if a is None:
                a = cum[mno] = [0, 0, 0, 0]
            a[0] += c[0]; a[1] += c[1]; a[2] += c[2]; a[3] += c[3]
    tot = 0.0
    n = 0
    for mno, rate in teacher_v.items():
        a = cum.get(mno)
        if a is None or a[0] == 0:
            continue
        tot += abs(a[2] / a[0] * 100.0 - rate)
        n += 1
    if n == 0:
        return None, 0
    return tot / n, n


def main():
    if not os.path.exists(USAGE):
        print("motorUsage.json が無い。先に buildMotorUsage.py を回すこと")
        sys.exit(1)
    u = json.load(open(USAGE, encoding="utf-8"))
    starts = {j: v["coverageFrom"] for j, v in u.get("venues", {}).items()}
    print("固定した coverageFrom: {}場".format(len(starts)))

    records = read_records()
    bv = by_venue_day(records)
    tdays = teacher_days()

    run("motors_all.csv（場ごと最終開催日）", B.load_teacher(), bv, starts, tdays)
    run("racers_today.csv（本日出走表）", load_today_teacher(), bv, starts, tdays)


if __name__ == "__main__":
    main()
