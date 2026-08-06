# -*- coding: utf-8 -*-
# buildCourseLast10.py
# 選手（登番）×進入コースごとの「直近10走の着順」を data/courseLast10.json に出力する。
#
# 着順の材料は results/YYYYMMDD.json（buildResults.py 出力・艇データ入り）。
# 進入コースの材料は取得期間で2つに分かれる。
#   ・2026-01-01以降 … preview/YYYYMMDD.json（buildPreview.py 出力）の racers[].course_number
#   ・2025年分       … preview/ に無いので旧 previews API から取る
#     https://raw.githubusercontent.com/BoatraceOpenAPI/previews/HEAD/docs/v2/YYYY/YYYYMMDD.json
#     このAPIの boats は日によって list と dict（キー"1"〜"6"）の両形式で来る。両方を受ける。
#
# 集計の決まり:
#   ・着は 1〜6 のみ採用。7以上（妨害・転覆・F・欠場等）はその走ごと除外してカウントしない。
#     「4着以下」に丸めると平均着順が実態より軽くなるため、母数から落とす方を選ぶ。
#   ・進入コースが取れない走も除外する（previews 側の欠損は実測1.4%）。
#   ・末尾10走に満たないコースは、あるだけを出す（n を必ず併記する）。
#   ・走が1つも無いコースはキーごと出さない。埋めない。
#
# 出力は数値のみ。判定・買い目・断定はここでは作らない（表示側の役割）。
import io
import os
import sys
import json
import glob
import time
import tempfile
import datetime
import urllib.request
from decimal import Decimal, ROUND_HALF_UP

RESULTS_DIR = "results"
PREVIEW_DIR = "preview"
OUT_PATH = os.path.join("data", "courseLast10.json")

# preview/ が存在するのは2026-01-01以降。それ以前は旧APIへ回す。
PREVIEW_FROM = "20260101"
LEGACY_BASE = "https://raw.githubusercontent.com/BoatraceOpenAPI/previews/HEAD/docs/v2/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) boatrace-data-collector"

LAST_N = 10
LANES = ["1", "2", "3", "4", "5", "6"]
JST = datetime.timezone(datetime.timedelta(hours=9))

# 全選手のコース別「直近10走の平均着順」の中央値。2025/7/15〜2026/8/4の実測。
# 直近10走が揃う選手のみで算出。毎日は再計算せず、この固定値を埋め込む。
MEDIAN = {"1": 2.1, "2": 3.2, "3": 3.3, "4": 3.7, "5": 4.0, "6": 4.5}

# 旧APIの取得結果はリポジトリ外に置く（追跡ファイルを増やさないため）。
CACHE_DIR = os.environ.get(
    "COURSE_LAST10_CACHE",
    os.path.join(tempfile.gettempdir(), "boatraceLegacyPreviews"),
)


def round2(v):
    """小数第2位で四捨五入。round() の偶数丸めを避ける。"""
    return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def raceNo(v):
    """レース表記("1R" 等)を整数にする。取れなければ None。"""
    s = str(v or "").strip().rstrip("Rr")
    return int(s) if s.isdigit() else None


def readJson(path):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def fetchLegacy(hd):
    """旧previews APIから指定日を取得。取れなければ None。取得分はキャッシュする。"""
    cache = os.path.join(CACHE_DIR, hd + ".json")
    hit = readJson(cache)
    if hit is not None:
        return hit
    url = "{0}{1}/{2}.json".format(LEGACY_BASE, hd[:4], hd)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
            break
        except Exception:
            time.sleep(1 + i * 2)
    if not raw or len(raw) < 20:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with io.open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        pass
    return data


def boatRows(boats):
    """previews API の boats を配列に均す。list と dict（キー"1"〜"6"）の両形式に対応。"""
    if isinstance(boats, list):
        return [b for b in boats if isinstance(b, dict)]
    if isinstance(boats, dict):
        rows = []
        for k in sorted(boats, key=lambda x: int(x) if str(x).isdigit() else 99):
            b = boats[k]
            if not isinstance(b, dict):
                continue
            if b.get("racer_boat_number") is None:
                # dict形式ではキーが枠番。値側に枠番が無い日があるので補う。
                b = dict(b)
                b["racer_boat_number"] = int(k) if str(k).isdigit() else None
            rows.append(b)
        return rows
    return []


def courseMapLocal(hd):
    """preview/YYYYMMDD.json から (場, レース, 枠) -> 進入コース を作る。"""
    data = readJson(os.path.join(PREVIEW_DIR, hd + ".json"))
    if not data:
        return None
    cmap = {}
    for row in (data.get("直前情報") or []):
        try:
            sn = int(row.get("stadium_number") or int(row.get("場コード")))
        except Exception:
            continue
        rn = row.get("race_number") or raceNo(row.get("レース"))
        if not rn:
            continue
        for b in (row.get("racers") or []):
            waku = b.get("entry_number")
            course = b.get("course_number")
            if waku is None or course is None:
                continue
            cmap[(sn, int(rn), int(waku))] = int(course)
    return cmap


def courseMapLegacy(hd):
    """旧previews APIから (場, レース, 枠) -> 進入コース を作る。"""
    data = fetchLegacy(hd)
    if not data:
        return None
    cmap = {}
    for row in (data.get("previews") or []):
        sn = row.get("race_stadium_number")
        rn = row.get("race_number")
        if sn is None or rn is None:
            continue
        for b in boatRows(row.get("boats")):
            waku = b.get("racer_boat_number")
            course = b.get("racer_course_number")
            if waku is None or course is None:
                continue
            cmap[(int(sn), int(rn), int(waku))] = int(course)
    return cmap


def courseMap(hd):
    """その日の進入コース表。preview/ を優先し、無ければ旧APIへ回す。"""
    if hd >= PREVIEW_FROM:
        cmap = courseMapLocal(hd)
        if cmap:
            return cmap, "preview"
    cmap = courseMapLegacy(hd)
    if cmap:
        return cmap, "legacy"
    return None, "none"


def main():
    t0 = time.time()
    days = sorted(
        os.path.basename(p)[:-5]
        for p in glob.glob(os.path.join(RESULTS_DIR, "*.json"))
    )
    if not days:
        print("no results", file=sys.stderr)
        return 1

    # 登番 -> [(開催日, 進入コース, 着), ...] を時系列（日 → 場 → レース → 枠）で積む
    runs = {}
    used = []
    noCourseDay = []
    skipNoCourse = 0
    skipChaku = 0
    total = 0

    for hd in days:
        res = readJson(os.path.join(RESULTS_DIR, hd + ".json"))
        if not res:
            continue
        cmap, src = courseMap(hd)
        if not cmap:
            noCourseDay.append(hd)
            continue
        rows = []
        for row in (res.get("結果") or []):
            try:
                sn = int(row.get("場コード"))
            except Exception:
                continue
            rn = raceNo(row.get("レース"))
            if not rn:
                continue
            rows.append((sn, rn, row))
        rows.sort(key=lambda x: (x[0], x[1]))
        for sn, rn, row in rows:
            for b in sorted((row.get("艇") or []), key=lambda x: x.get("枠") or 9):
                total += 1
                no = b.get("登番")
                waku = b.get("枠")
                chaku = b.get("着")
                if no is None or waku is None:
                    continue
                course = cmap.get((sn, rn, int(waku)))
                if course is None:
                    skipNoCourse += 1
                    continue
                if not isinstance(chaku, int) or chaku < 1 or chaku > 6:
                    # 7以上（妨害・転覆・F・欠場等）はその走ごと落とす
                    skipChaku += 1
                    continue
                runs.setdefault(str(no), []).append((hd, int(course), chaku))
        used.append((hd, src))

    players = {}
    for no in sorted(runs, key=lambda x: int(x)):
        seq = runs[no]
        out = {}
        for lane in LANES:
            hits = [r for r in seq if r[1] == int(lane)]
            if not hits:
                continue  # 走が無いコースはキーごと出さない
            tail = hits[-LAST_N:]
            chaku = [r[2] for r in tail]
            out[lane] = {
                "n": len(chaku),
                "chaku": chaku,
                "avg": round2(sum(chaku) / float(len(chaku))),
                "from": tail[0][0],
                "to": tail[-1][0],
            }
        mix = {}
        for r in seq[-LAST_N:]:  # mix はコース不問の直近10走
            k = str(r[1])
            mix[k] = mix.get(k, 0) + 1
        if mix:
            out["mix"] = {k: mix[k] for k in LANES if k in mix}
        if out:
            players[no] = out

    obj = {
        "生成時刻": datetime.datetime.now(JST).isoformat(timespec="seconds"),
        "集計期間": {"from": used[0][0], "to": used[-1][0]},
        "中央値": MEDIAN,
        "選手": players,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with io.open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))

    legacy = sum(1 for _, s in used if s == "legacy")
    print("wrote", OUT_PATH,
          "players", len(players),
          "days", len(used), "(legacy", str(legacy) + ")",
          "bytes", os.path.getsize(OUT_PATH))
    print("skipped: 進入コース無し", skipNoCourse, "/ 着7以上・欠測", skipChaku,
          "/ 枠数", total)
    if noCourseDay:
        # 無言で落とすと「集計できた日」と区別がつかなくなるので必ず出す
        print("進入コースを取得できなかった日", len(noCourseDay), noCourseDay)
    print("elapsed %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
