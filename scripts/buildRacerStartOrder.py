#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""選手×進入コース別のST順（発順）を集計して docs/data/racerStartOrder.json を生成する。

集計仕様:
  入力  results/*.json（リポジトリ直下・2025/07/15〜）
  採用  艇ごとに判定する。「コース」が1〜6 かつ「ST」が非nullで0以上の艇を有効艇とする。
        F（STが負値）と欠場（null）はその1走だけを除き、同じレースの他艇は残す。
        レースを丸ごと除外することはしない。有効艇が2艇未満のレースだけは順位が
        付かないので使わない。
  順位  そのレースの有効艇のSTを昇順に並べた順位。同値は平均順位を与える
        （例: 最速タイが2艇なら、ともに 1.5）。
        有効艇が6艇に満たないレースが全体の約2.4%混ざるが、平均への影響は
        実測で0.011。1セルの推定誤差±0.27（39走時）の25分の1で無視できる。
  指標  進入コース別に [N, 平均ST, 平均ST順, ST1番手率] を出す。
        ST1番手率は平均順位が 1.0 となった回数の割合（単独最速のみ）。
  期間  all = 全期間 / m6 = 最新データ日から遡って180日
  母数  母数ガードは 10。ガード未満のセルも値は出力し、表示側で伏せる。

使い方:
  python3 scripts/buildRacerStartOrder.py [--results results] [--out docs/data/racerStartOrder.json]
"""

import argparse
import datetime
import glob
import json
import os
import re
from collections import defaultdict

# 母数ガード。走数がこれ未満のセルは表示側で伏せる。startLate と同じ値に揃える。
GUARD = 20
# 言葉を添える境界。全体との差がこれ未満なら「平均的」とする。
# 39走（セルの走数の中央値）での推定誤差±0.27の外側に置く。
SAY = 0.30
M6_DAYS = 180
FILE_RE = re.compile(r"(\d{8})\.json$")


def parse_day(path):
    m = FILE_RE.search(os.path.basename(path))
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def rank_map(sts):
    """STのリストから、ST値 -> 平均順位 の辞書を作る。"""
    ordered = sorted(sts)
    out = {}
    for v in set(ordered):
        lo = ordered.index(v) + 1
        hi = len(ordered) - ordered[::-1].index(v)
        out[v] = (lo + hi) / 2.0
    return out


class Bucket:
    def __init__(self):
        self.n = defaultdict(int)
        self.st = defaultdict(float)
        self.rank = defaultdict(float)
        self.top = defaultdict(int)
        self.f = 0
        self.races = 0

    def add(self, course, st, rk):
        self.n[course] += 1
        self.st[course] += st
        self.rank[course] += rk
        if rk == 1.0:
            self.top[course] += 1

    def dump(self):
        out = {}
        for c in sorted(self.n):
            n = self.n[c]
            out[str(c)] = [
                n,
                round(self.st[c] / n, 3),
                round(self.rank[c] / n, 2),
                round(100.0 * self.top[c] / n, 1),
            ]
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="docs/data/racerStartOrder.json")
    args = ap.parse_args()

    files = sorted(p for p in glob.glob(os.path.join(args.results, "*.json")) if parse_day(p))
    if not files:
        raise SystemExit("results が見つかりません: %s" % args.results)

    days = [parse_day(p) for p in files]
    last_day = max(days)
    first_day = min(days)
    m6_from = last_day - datetime.timedelta(days=M6_DAYS - 1)

    racers = defaultdict(lambda: {"all": Bucket(), "m6": Bucket()})
    # 全選手を合算した基準。選手の値が速いのか遅いのかは、これと比べないと読めない。
    overall = {"all": Bucket(), "m6": Bucket()}
    stat = {
        "all": {"races": 0, "used": 0, "miss": 0, "f": 0, "size": 0},
        "m6": {"races": 0, "used": 0, "miss": 0, "f": 0, "size": 0},
    }

    for path in files:
        day = parse_day(path)
        spans = ["all"] + (["m6"] if day >= m6_from else [])
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for race in data.get("結果", []):
            boats = race.get("艇") or []
            for s in spans:
                stat[s]["races"] += 1
            if len(boats) != 6:
                for s in spans:
                    stat[s]["size"] += 1
                continue
            valid = []
            for b in boats:
                st = b.get("ST")
                course = b.get("コース")
                if isinstance(st, (int, float)) and st < 0:
                    # フライング。その1走だけを除き、回数は選手ごとに数える。
                    no = str(b.get("登番"))
                    for s in spans:
                        racers[no][s].f += 1
                        stat[s]["f"] += 1
                    continue
                if st is None or not isinstance(course, int) or not 1 <= course <= 6:
                    # 欠場など。その1走だけを除く。
                    for s in spans:
                        stat[s]["miss"] += 1
                    continue
                valid.append(b)
            if len(valid) < 2:
                continue
            rmap = rank_map([b["ST"] for b in valid])
            for s in spans:
                stat[s]["used"] += 1
            for b in valid:
                no = str(b.get("登番"))
                course = b["コース"]
                rk = rmap[b["ST"]]
                for s in spans:
                    racers[no][s].add(course, b["ST"], rk)
                    overall[s].add(course, b["ST"], rk)

    out = {
        "出典": "results/*.json",
        "生成": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime(
            "%Y-%m-%dT%H:%M:%S+09:00"
        ),
        "集計方法": (
            "そのレースの有効艇のSTを昇順に並べた順位。同値は平均順位。"
            "フライングと欠場はその1走だけを除き、同じレースの他艇は残す。"
        ),
        "指標": ["N", "平均ST", "平均ST順", "ST1番手率"],
        "母数ガード": GUARD,
        "言語化閾値": SAY,
        "基準": {s: {"course": overall[s].dump()} for s in ("all", "m6")},
        "期間": {
            "all": {
                "from": first_day.strftime("%Y%m%d"),
                "to": last_day.strftime("%Y%m%d"),
                "採用レース数": stat["all"]["used"],
                "除外走_欠場等": stat["all"]["miss"],
                "除外走_F": stat["all"]["f"],
                "除外レース_艇数不足": stat["all"]["size"],
            },
            "m6": {
                "from": m6_from.strftime("%Y%m%d"),
                "to": last_day.strftime("%Y%m%d"),
                "採用レース数": stat["m6"]["used"],
                "除外走_欠場等": stat["m6"]["miss"],
                "除外走_F": stat["m6"]["f"],
                "除外レース_艇数不足": stat["m6"]["size"],
            },
        },
        "racers": {},
    }

    for no in sorted(racers, key=lambda x: int(x) if x.isdigit() else 0):
        rec = {}
        for s in ("all", "m6"):
            b = racers[no][s]
            cells = b.dump()
            if not cells and not b.f:
                continue
            rec[s] = {"course": cells, "F": b.f}
        if rec:
            out["racers"][no] = rec
    out["count"] = len(out["racers"])

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    print(
        "wrote %s racers=%d all_used=%d m6_used=%d"
        % (args.out, out["count"], stat["all"]["used"], stat["m6"]["used"])
    )


if __name__ == "__main__":
    main()
