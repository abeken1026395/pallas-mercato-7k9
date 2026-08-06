# -*- coding: utf-8 -*-
"""
buildCourseLast10.py

選手ごとに「そのコースでの直近10走の着順」を積み上げる。

入力:
  results/YYYYMMDD.json   着順と登番。2025/7/15 以降。
  preview/YYYYMMDD.json   進入コース。2026/1/1 以降しか無い。
  BoatraceOpenAPI previews (v2)
                          2025年分の進入コース。preview/ が無い日はここから取る。
                          https://raw.githubusercontent.com/BoatraceOpenAPI/previews/HEAD/docs/v2/{YYYY}/{YYYYMMDD}.json
                          このAPIは boats が日によって list と dict("1"〜"6") の
                          両方の形で返る。どちらでも読めるようにしてある。

出力:
  data/courseLast10.json  （docs/ ではない。表示側の取り込みは別フェーズ）

集計ルール:
  - 着は 1〜6 のみ採用。7以上（妨害・転覆・F・欠場等の内部表現）はその走ごと捨てる。
  - 進入コースが取れない走も捨てる。
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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import urllib.error
import urllib.request

# ---- 設定 ----
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(REPO_ROOT, "results")
PREVIEW_DIR = os.path.join(REPO_ROOT, "preview")
OUT_PATH = os.path.join(REPO_ROOT, "data", "courseLast10.json")

PREVIEW_API = (
    "https://raw.githubusercontent.com/BoatraceOpenAPI/previews/HEAD"
    "/docs/v2/{year}/{hd}.json"
)
API_WORKERS = 8
API_RETRY = 3

LAST_N = 10
JST = timezone(timedelta(hours=9))

# 全選手のコース別平均着順の中央値。
# 2025/7/15〜2026/8/4の実測。直近10走が揃う選手のみで算出。
MEDIAN = {"1": 2.1, "2": 3.2, "3": 3.3, "4": 3.7, "5": 4.0, "6": 4.5}


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


def iterBoats(boats):
    """boats が list でも dict("1"〜"6") でも要素を順に返す。"""
    if isinstance(boats, list):
        for b in boats:
            if isinstance(b, dict):
                yield b
    elif isinstance(boats, dict):
        for k in sorted(boats.keys(), key=lambda x: (len(str(x)), str(x))):
            b = boats[k]
            if isinstance(b, dict):
                yield b


def courseMapFromPreview(doc):
    """preview/YYYYMMDD.json → {(場コード, レース番号, 枠): 進入コース}"""
    out = {}
    for race in doc.get("直前情報", []) or []:
        jcd = normStadium(race.get("場コード", race.get("stadium_number")))
        rno = normRaceNo(race.get("レース", race.get("race_number")))
        if jcd is None or rno is None:
            continue
        for b in race.get("racers", []) or []:
            waku = b.get("entry_number")
            course = b.get("course_number")
            if waku is None or course is None:
                continue
            out[(jcd, rno, int(waku))] = int(course)
    return out


def courseMapFromApi(doc):
    """BoatraceOpenAPI previews v2 → {(場コード, レース番号, 枠): 進入コース}"""
    races = doc.get("previews", doc) if isinstance(doc, dict) else doc
    if isinstance(races, dict):
        races = list(races.values())
    out = {}
    for race in races or []:
        if not isinstance(race, dict):
            continue
        jcd = normStadium(race.get("race_stadium_number"))
        rno = normRaceNo(race.get("race_number"))
        if jcd is None or rno is None:
            continue
        for b in iterBoats(race.get("boats")):
            waku = b.get("racer_boat_number")
            course = b.get("racer_course_number")
            if waku is None or course is None:
                continue
            out[(jcd, rno, int(waku))] = int(course)
    return out


def fetchApi(hd):
    """2025年分などの進入コースを外部APIから取る。取れなければ None。"""
    url = PREVIEW_API.format(year=hd[:4], hd=hd)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(API_RETRY):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == API_RETRY - 1:
                return None
        except Exception:
            if attempt == API_RETRY - 1:
                return None
        time.sleep(1.0 + attempt)
    return None


def buildCourseMaps(dates):
    """日付ごとの進入コースmapを作る。preview/ を優先し、無い日だけAPIを叩く。"""
    maps = {}
    needApi = []
    for hd in dates:
        p = os.path.join(PREVIEW_DIR, hd + ".json")
        if os.path.isfile(p):
            try:
                maps[hd] = courseMapFromPreview(loadJson(p))
                continue
            except Exception as e:
                print("preview読めず %s: %s" % (hd, e), file=sys.stderr)
        needApi.append(hd)

    if needApi:
        print("外部APIから進入コースを取得: %d日" % len(needApi), file=sys.stderr)
        with ThreadPoolExecutor(max_workers=API_WORKERS) as ex:
            for hd, doc in zip(needApi, ex.map(fetchApi, needApi)):
                if doc is None:
                    maps[hd] = {}
                    print("  進入コース取得できず: %s" % hd, file=sys.stderr)
                else:
                    maps[hd] = courseMapFromApi(doc)
    return maps


def collectRuns(dates, courseMaps):
    """
    (登番) → [(日付, 場コード, レース番号, 進入コース, 着), ...] を時系列順で作る。
    着 1〜6 かつ 進入コースが取れた走だけ。
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
        cmap = courseMaps.get(hd, {})
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
                waku = b.get("枠")
                if toban is None or waku is None:
                    stat["登番/枠なし"] += 1
                    continue
                if not isinstance(chaku, int) or chaku < 1 or chaku > 6:
                    stat["着が1〜6でない"] += 1
                    continue
                course = cmap.get((jcd, rno, int(waku)))
                if course is None or not (1 <= int(course) <= 6):
                    stat["進入コースなし"] += 1
                    continue
                runs[str(toban)].append((hd, jcd, rno, int(course), int(chaku)))
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

    courseMaps = buildCourseMaps(dates)
    runs, stat = collectRuns(dates, courseMaps)
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
