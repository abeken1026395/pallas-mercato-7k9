# -*- coding: utf-8 -*-
"""
buildMaezuke.py

選手ごとに「前づけして枠より内のコースに入ったとき、何着だったか」を数える
（2026-10-26 けん裁定：選手別・出走表に出す・毎日更新）。

入力:
  results/YYYYMMDD.json   艇[].枠・コース・着・登番。2025/7/15 以降。外部アクセスは無い。

出力:
  docs/data/maezuke.json  出走表（template_racers.html）が fetch する。

前づけした艇の決め方:
  - 欠場（着16）とコースの欠けた艇を除き、残った艇の「枠の順」と「コースの順」を比べる。
  - コースの順に並べた枠番号から、順番を崩さずに残せるいちばん長い並び（最長増加部分列）を取り、
    そこに入らなかった艇を「動いた艇」とする。長さの同じ並びが複数あるときは、
    内へ動いた艇が多くなる並びを選ぶ（前づけは自分から動くもので、外へ1つ下がるだけの例は少ないため）。
  - 動いた艇のうち、コースの順位が枠の順位より内のものを「前づけ」とする。
    こうすると、2枠が6コースへ回って3〜6枠が1つずつ内へずれただけの艇は前づけに入らない。

集計:
  - 着は 1・2・3 着を数える。着コード 7〜15（妨害・転覆・失格等）は着外として分母に残す。16（欠場）は除く。
  - 選手ごとに、合計と、入ったコースごとの [走, 1着, 2着, 3着]。
  - 率は出走表側で、20走以上のときだけ出す（ここでは回数だけを持つ）。
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from itertools import combinations

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.environ.get("MAEZUKE_RESULTS", os.path.join(REPO_ROOT, "results"))
OUT_PATH = os.path.join(REPO_ROOT, "docs", "data", "maezuke.json")
JST = timezone(timedelta(hours=9))


def movers(boats):
    """boats: [(枠, コース)]。前づけした艇の枠の集合を返す。"""
    waku_rank = {w: i for i, (w, _) in enumerate(sorted(boats))}
    by_course = [w for w, _ in sorted(boats, key=lambda x: x[1])]
    course_rank = {w: i for i, w in enumerate(by_course)}
    n = len(by_course)
    if by_course == sorted(by_course):
        return set()
    best = None
    for k in range(n, 0, -1):
        for keep in combinations(range(n), k):
            seq = [by_course[i] for i in keep]
            if seq != sorted(seq):
                continue
            moved = [by_course[i] for i in range(n) if i not in keep]
            inward = sum(1 for w in moved if course_rank[w] < waku_rank[w])
            if best is None or inward > best[0]:
                best = (inward, moved)
        if best is not None:
            break
    return {w for w in best[1] if course_rank[w] < waku_rank[w]}


def main():
    files = sorted(f for f in os.listdir(RESULTS_DIR) if f.endswith(".json") and f[:8].isdigit())
    per = defaultdict(lambda: [0, 0, 0, 0, defaultdict(lambda: [0, 0, 0, 0])])
    names = {}
    races = 0
    d0 = d1 = None
    for f in files:
        try:
            d = json.load(open(os.path.join(RESULTS_DIR, f), encoding="utf-8"))
        except Exception:
            continue
        for r in d.get("結果") or []:
            bs = []
            for b in r.get("艇") or []:
                c, w, t = b.get("コース"), b.get("枠"), b.get("着")
                if not isinstance(c, int) or not isinstance(w, int) or t == 16 or not b.get("登番"):
                    continue
                bs.append(b)
            if len(bs) < 2 or len({b["コース"] for b in bs}) != len(bs):
                continue
            races += 1
            d0 = d0 or f[:8]
            d1 = f[:8]
            mv = movers([(b["枠"], b["コース"]) for b in bs])
            if not mv:
                continue
            crank = {b["枠"]: i + 1 for i, b in enumerate(sorted(bs, key=lambda x: x["コース"]))}
            for b in bs:
                if b["枠"] not in mv:
                    continue
                tb = str(b["登番"])
                names[tb] = b.get("氏名") or ""
                t = b.get("着")
                c = crank[b["枠"]]
                rec = per[tb]
                for row in (rec, rec[4][c]):
                    row[0] += 1
                    if t in (1, 2, 3):
                        row[t] += 1
    out = {
        "出典": "results/（公式 競走成績）",
        "期間": [d0, d1],
        "レース数": races,
        "生成": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "定義": "前づけ＝進入の並びで順番を崩して枠より内のコースに入った艇。ほかの艇が外へ回って内へずれただけの艇は含めない。コースは欠場を除いた並びの順位。",
        "形式": "選手[登番] = [走, 1着, 2着, 3着, {入ったコース: [走, 1着, 2着, 3着]}]",
        "選手": {tb: [v[0], v[1], v[2], v[3], {str(c): x for c, x in sorted(v[4].items())}] for tb, v in sorted(per.items())},
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(",", ":"))
    tot = sum(v[0] for v in per.values())
    print(f"maezuke: {len(files)}日 {races}レース 前づけ延べ{tot}走 選手{len(per)}人 "
          f"20走以上{sum(1 for v in per.values() if v[0] >= 20)}人 → {OUT_PATH} {os.path.getsize(OUT_PATH):,}B")


if __name__ == "__main__":
    sys.exit(main())
