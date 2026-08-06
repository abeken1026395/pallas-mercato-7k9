# -*- coding: utf-8 -*-
"""
buildCourseLast10.py

選手ごとに「そのコースでの直近10走の着順」を積み上げる。

入力:
  results/YYYYMMDD.json   着順・登番・進入コース。2025/7/15 以降。
                          艇[].コース に実際の進入コースが入っているので、
                          このファイルだけで完結する。外部アクセスは無い。

出力:
  data/courseLast10.json  （docs/ ではない。表示側の取り込みは別フェーズ）
                          毎日変わる中間データなのでコミットしない。

集計ルール:
  - 着は 1〜6 のみ採用。7以上（妨害・転覆・F・欠場等の内部表現）はその走ごと捨てる。
  - コースが欠損している走も捨てる。
  - コース別に時系列の末尾10走を取る。10走に満たなければあるだけ。
  - mix はコース不問で直近10走を取り、その進入コースを数えたもの。
  - 走が1つも無いコースはキーごと出さない。
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta

# ---- 設定 ----
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(REPO_ROOT, "results")
OUT_PATH = os.path.join(REPO_ROOT, "data", "courseLast10.json")

LAST_N = 10
JST = timezone(timedelta(hours=9))

# 全選手のコース別平均着順の中央値。
# 2025/7/15〜2026/8/6の実測（results基準）。直近10走が揃う選手のみで算出。
MEDIAN = {"1": 2.1, "2": 3.2, "3": 3.3, "4": 3.6, "5": 4.0, "6": 4.5}


def loadJson(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def listResultDates(dateFrom, dateTo):
    """results/ にある YYYYMMDD.json を昇順で返す。"""
    out = []
    if not os.path.isdir(RESULTS_DIR):
        return out
    for name in os.listdir(RESULTS_DIR):
        if not name.endswith(".json"):
            continue
        hd = name[:-5]
        if len(hd) != 8 or not hd.isdigit():
            continue
        if dateFrom and hd < dateFrom:
            continue
        if dateTo and hd > dateTo:
            continue
        out.append(hd)
    out.sort()
    return out


def normStadium(v):
    """場コードを2桁ゼロ埋めの文字列に揃える。"""
    if v is None:
        return None
    s = str(v).strip()
    if s.isdigit():
        return "%02d" % int(s)
    return s


def normRaceNo(v):
    """レース番号を int に揃える。'1R' でも 1 でも受ける。"""
    if v is None:
        return None
    s = str(v).strip()
    if s.endswith("R") or s.endswith("r"):
        s = s[:-1]
    if not s.isdigit():
        return None
    return int(s)


def collectRuns(dates):
    """
    (登番) → [(日付, 場コード, レース番号, 進入コース, 着), ...] を時系列順で作る。
    着 1〜6 かつ コースが取れた走だけ。
    """
    runs = defaultdict(list)
    stat = Counter()
    for hd in dates:
        path = os.path.join(RESULTS_DIR, hd + ".json")
        try:
            doc = loadJson(path)
        except Exception as e:
            print("results読めず %s: %s" % (hd, e), file=sys.stderr)
            continue
        rows = []
        for race in doc.get("結果", []) or []:
            jcd = normStadium(race.get("場コード"))
            rno = normRaceNo(race.get("レース"))
            if jcd is None or rno is None:
                continue
            rows.append((jcd, rno, race))
        # 同じ日の中は 場コード → レース番号 の順で時系列とみなす
        rows.sort(key=lambda x: (x[0], x[1]))
        for jcd, rno, race in rows:
            for b in race.get("艇", []) or []:
                stat["走"] += 1
                toban = b.get("登番")
                chaku = b.get("着")
                course = b.get("コース")
                if toban is None:
                    stat["登番なし"] += 1
                    continue
                # 2つの除外条件は独立に数える（同じ走が両方に該当することがある）
                okChaku = isinstance(chaku, int) and 1 <= chaku <= 6
                okCourse = isinstance(course, int) and 1 <= course <= 6
                if not okChaku:
                    stat["着が1〜6でない"] += 1
                if not okCourse:
                    stat["コース欠損"] += 1
                if not okChaku or not okCourse:
                    continue
                runs[str(toban)].append((hd, jcd, rno, course, chaku))
                stat["採用"] += 1
    return runs, stat


def buildRacer(seq):
    """1選手分。seq は時系列順の (日付, 場, R, コース, 着)。"""
    out = {}
    byCourse = defaultdict(list)
    for hd, jcd, rno, course, chaku in seq:
        byCourse[str(course)].append((hd, chaku))

    for course in ("1", "2", "3", "4", "5", "6"):
        items = byCourse.get(course)
        if not items:
            # 走が1つも無いコースはキーごと出さない
            continue
        tail = items[-LAST_N:]
        chakus = [c for _, c in tail]
        out[course] = {
            "n": len(tail),
            "chaku": chakus,
            # 小数第2位で四捨五入（＝小数第1位まで残す）
            "avg": round(sum(chakus) / float(len(chakus)), 1),
            "from": tail[0][0],
            "to": tail[-1][0],
        }

    # mix はコース不問で直近10走
    mixTail = seq[-LAST_N:]
    mix = Counter(str(course) for _, _, _, course, _ in mixTail)
    out["mix"] = {k: mix[k] for k in sorted(mix.keys())}
    return out


def main():
    started = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dateFrom", default="20250715")
    ap.add_argument("--to", dest="dateTo", default=None)
    args = ap.parse_args()

    dates = listResultDates(args.dateFrom, args.dateTo)
    if not dates:
        print("results/ に対象日がない", file=sys.stderr)
        return 1
    print("対象日: %d日 (%s〜%s)" % (len(dates), dates[0], dates[-1]), file=sys.stderr)

    runs, stat = collectRuns(dates)
    print("走数: %s" % dict(stat), file=sys.stderr)

    racers = {}
    for toban in sorted(runs.keys(), key=lambda x: int(x)):
        racers[toban] = buildRacer(runs[toban])

    doc = {
        "生成時刻": datetime.now(JST).replace(microsecond=0).isoformat(),
        "集計期間": {"from": dates[0], "to": dates[-1]},
        "中央値": MEDIAN,
        "選手": racers,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(
        "出力: %s  選手%d人  %.1f秒"
        % (OUT_PATH, len(racers), time.time() - started),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
