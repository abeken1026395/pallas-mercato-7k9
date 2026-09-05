#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""選手×進入コース別の入着分布を集計して docs/data/racerCourseStats.json を生成する。

集計仕様:
  入力  results/*.json（リポジトリ直下・2025/07/15〜）
  基準  進入コース（艇の「コース」）。枠番ではない。枠番と進入コースは全体で
        約8%ずれるため、枠番で数えると前づけする選手の姿が消える。
  採用  艇ごとに判定する。「コース」が1〜6 かつ「着」が 1〜15 の艇を数える。
        欠場（16）・99・null はその1走だけを分母から除き、同じレースの他艇は残す。
        レースを丸ごと除外することはしない。
  区分  docs/data/courseFinish.json（全体版）と同じ区分に揃える。
        c1=1着 / c2=2着 / c3=3着 / c4plus=4〜6着 / dq=着が7〜15（妨害・転覆・
        F・失格など）。dq は分母に含める。n = c1+c2+c3+c4plus+dq。
  保持  回数だけを持つ。率は表示側で計算する（丸め誤差を作らないため）。
  期間  全期間の1本のみ。直近6ヶ月では母数が足りず、二項の率は出せない
        （実測：180日窓では 20走以上のセルが32.2%、選手の28%が1コースも出せない）。
  母数  母数ガードは 20。ガード未満のセルも回数は出力し、表示側で率を伏せて
        実数だけを出す。

使い方:
  python3 scripts/buildRacerCourseStats.py [--results results] [--out docs/data/racerCourseStats.json]
"""

import argparse
import datetime
import glob
import json
import os
import re
from collections import defaultdict

# 率を出してよい最低走数。startLate・racerStartOrder と同じ値に揃える。
GUARD = 20
FILE_RE = re.compile(r"(\d{8})\.json$")


def parse_day(path):
    m = FILE_RE.search(os.path.basename(path))
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


class Bucket:
    """進入コース別に [n, c1, c2, c3, c4plus, dq] を貯める。"""

    IDX = ["n", "c1", "c2", "c3", "c4plus", "dq"]

    def __init__(self):
        self.cell = defaultdict(lambda: [0, 0, 0, 0, 0, 0])

    def add(self, course, chaku):
        row = self.cell[course]
        row[0] += 1
        if chaku == 1:
            row[1] += 1
        elif chaku == 2:
            row[2] += 1
        elif chaku == 3:
            row[3] += 1
        elif 4 <= chaku <= 6:
            row[4] += 1
        else:
            row[5] += 1

    def dump(self):
        return {str(c): self.cell[c] for c in sorted(self.cell)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="docs/data/racerCourseStats.json")
    args = ap.parse_args()

    files = sorted(p for p in glob.glob(os.path.join(args.results, "*.json")) if parse_day(p))
    if not files:
        raise SystemExit("results が見つかりません: %s" % args.results)

    days = [parse_day(p) for p in files]
    first_day, last_day = min(days), max(days)

    racers = defaultdict(Bucket)
    overall = Bucket()
    stat = {"races": 0, "boats": 0, "used": 0, "skip_kesu": 0, "skip_course": 0}

    for path in files:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for race in data.get("結果", []):
            stat["races"] += 1
            for b in race.get("艇") or []:
                stat["boats"] += 1
                course = b.get("コース")
                chaku = b.get("着")
                no = b.get("登番")
                if not isinstance(chaku, int) or not 1 <= chaku <= 15:
                    # 欠場(16)・99・null。その1走だけを分母から除く。
                    stat["skip_kesu"] += 1
                    continue
                if no is None or not isinstance(course, int) or not 1 <= course <= 6:
                    # 進入コースが取れない走。数えようがないので分母から除く。
                    stat["skip_course"] += 1
                    continue
                stat["used"] += 1
                racers[str(no)].add(course, chaku)
                overall.add(course, chaku)

    out = {
        "出典": "results/*.json",
        "生成": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=9))
        ).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "集計方法": (
            "進入コース別の入着回数。枠番ではない。"
            "欠場はその1走だけを分母から除き、同じレースの他艇は残す。"
            "着が7〜15（妨害・転覆・F・失格など）は dq として分母に含める。"
        ),
        "指標": Bucket.IDX,
        "定義": {
            "n": "その進入コースで走った回数（dq を含む）",
            "c1": "1着",
            "c2": "2着",
            "c3": "3着",
            "c4plus": "4〜6着",
            "dq": "着が7〜15（妨害・エンスト・転覆・落水・沈没・不完走・失格・F・L）",
            "率": "各区分 ÷ n。JSONは回数だけを持ち、率は表示側で計算する",
        },
        "母数ガード": GUARD,
        "期間": {
            "from": first_day.strftime("%Y%m%d"),
            "to": last_day.strftime("%Y%m%d"),
            "日数": len(files),
            "レース数": stat["races"],
            "採用走": stat["used"],
            "除外走_欠場等": stat["skip_kesu"],
            "除外走_コース不明": stat["skip_course"],
        },
        "基準": {"course": overall.dump()},
        "racers": {},
    }

    for no in sorted(racers, key=lambda x: int(x) if x.isdigit() else 0):
        out["racers"][no] = racers[no].dump()
    out["count"] = len(out["racers"])

    d = os.path.dirname(args.out)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    print(
        "wrote %s racers=%d used=%d races=%d"
        % (args.out, out["count"], stat["used"], stat["races"])
    )


if __name__ == "__main__":
    main()
