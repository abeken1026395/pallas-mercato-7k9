# -*- coding: utf-8 -*-
# fetchResultsV2.py
# 旧取得元 BoatraceOpenAPI/results v2 から過去日の結果を1日ずつ取得し、
# results/YYYYMMDD.json と同じ形（2026-01-01以降の形）に変換してリポジトリの外へ保存する。
#
# 取得元: https://raw.githubusercontent.com/BoatraceOpenAPI/results/HEAD/docs/v2/YYYY/YYYYMMDD.json
#   ・v2 で 200 が返る最古日は 2017-10-25（2017-10-24 は 404。2026-09-16 実測）。
#   ・v2 には級別が無い。艇の "級別" / "級別コード" は null で持つ（取れなかったものは埋めない）。
#   ・3連単の払戻が無いレース（不成立など）は buildResults.py と同じく落とす。
#   ・風向・天候はコード値のまま。換算はしない。
#
# 本線（buildResults.py / updateResults.yml / updateResultsLive.yml）とは独立。
# リポジトリの results/ には書かない。出力先がリポジトリ内なら停止する。
#
# 使い方:
#   py -3 scripts/fetchResultsV2.py --start 20171025 --end 20250714
#   途中で止めても同じコマンドで再開できる（進捗は <out>/_progress.json）。
#
# 出力:
#   <out>/YYYYMMDD.json            変換後（既定 C:\Users\USER\boatraceResults\json）
#   <raw>/YYYYMMDD.json.gz         取得した生JSON（既定 C:\Users\USER\boatraceResults\v2raw）
#   <out>/_progress.json           日付ごとの状態 done / failed と、レース数・試行回数
import argparse
import datetime
import gzip
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://raw.githubusercontent.com/BoatraceOpenAPI/results/HEAD/docs/v2/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) boatrace-data-collector"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MIN_INTERVAL = 1.5   # これ未満には詰めない
RETRIES = 3          # 初回に加えて最大3回

TECHNIQUE = {
    1: "逃げ", 2: "差し", 3: "まくり",
    4: "まくり差し", 5: "抜き", 6: "恵まれ",
}

PAYOUT_KEYS = [
    ("win", "単勝"),
    ("place", "複勝"),
    ("exacta", "2連単"),
    ("quinella", "2連複"),
    ("quinella_place", "拡連複"),
    ("trio", "3連複"),
    ("trifecta", "3連単"),
]


def _payouts(payouts):
    out = {}
    for key, label in PAYOUT_KEYS:
        rows = []
        for e in payouts.get(key, []) or []:
            combo = e.get("combination")
            pay = e.get("payout")
            if not combo or pay in (None, 0):
                continue
            try:
                rows.append({"組番": combo, "配当": int(pay)})
            except Exception:
                continue
        out[label] = rows
    return out


def to_races(data):
    """v2 の results 配列を results/*.json（2026-01-01以降の形）のレース配列に変換。"""
    races = []
    for r in data.get("results", []) or []:
        payouts = r.get("payouts") or {}
        tri = payouts.get("trifecta") or []
        if not tri:
            continue
        combo = tri[0].get("combination")
        pay = tri[0].get("payout")
        if not combo or pay in (None, 0):
            continue
        top3 = combo.split("-")
        if len(top3) != 3:
            continue
        try:
            boats = []
            for b in r.get("boats", []) or []:
                boats.append({
                    "枠": b.get("racer_boat_number"),
                    "登番": b.get("racer_number"),
                    "氏名": b.get("racer_name"),
                    "コース": b.get("racer_course_number"),
                    "ST": b.get("racer_start_timing"),
                    "着": b.get("racer_place_number"),
                    "級別": None,
                    "級別コード": None,
                })
            tech_no = r.get("race_technique_number")
            try:
                tech_no = int(tech_no) if tech_no is not None else None
            except Exception:
                tech_no = None
            races.append({
                "場コード": "%02d" % int(r["race_stadium_number"]),
                "レース": "%dR" % int(r["race_number"]),
                "着順": combo,
                "1着": int(top3[0]), "2着": int(top3[1]), "3着": int(top3[2]),
                "三連単配当": int(pay),
                "決まり手": TECHNIQUE.get(tech_no),
                "払戻": _payouts(payouts),
                "艇": boats,
                "レース日": r.get("race_date"),
                "風速": r.get("race_wind"),
                "風向コード": r.get("race_wind_direction_number"),
                "波高": r.get("race_wave"),
                "天候コード": r.get("race_weather_number"),
                "気温": r.get("race_temperature"),
                "水温": r.get("race_water_temperature"),
            })
        except Exception:
            continue
    return races


class Fetcher(object):
    """直列で取得し、前回リクエストから interval 秒以上あける。"""

    def __init__(self, interval):
        self.interval = max(MIN_INTERVAL, interval)
        self.last = 0.0

    def get(self, hd):
        wait = self.interval - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        url = "{0}{1}/{2}.json".format(BASE, hd[:4], hd)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, None
        except Exception as e:
            return "error:%s" % type(e).__name__, None
        finally:
            self.last = time.monotonic()


def _atomic_write(path, blob):
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)


def load_progress(path):
    if os.path.exists(path):
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"days": {}}


def save_progress(path, prog):
    _atomic_write(path, json.dumps(prog, ensure_ascii=False, indent=1).encode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYYMMDD")
    ap.add_argument("--end", required=True, help="YYYYMMDD")
    ap.add_argument("--out", default=r"C:\Users\USER\boatraceResults\json")
    ap.add_argument("--raw", default=r"C:\Users\USER\boatraceResults\v2raw")
    ap.add_argument("--interval", type=float, default=1.6)
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    raw = os.path.abspath(args.raw)
    for d in (out, raw):
        if os.path.normcase(d).startswith(os.path.normcase(REPO + os.sep)) or os.path.normcase(d) == os.path.normcase(REPO):
            sys.exit("出力先がリポジトリ内: %s" % d)
    os.makedirs(out, exist_ok=True)
    os.makedirs(raw, exist_ok=True)

    start = datetime.datetime.strptime(args.start, "%Y%m%d").date()
    end = datetime.datetime.strptime(args.end, "%Y%m%d").date()
    prog_path = os.path.join(out, "_progress.json")
    prog = load_progress(prog_path)
    days = prog["days"]
    fetcher = Fetcher(args.interval)
    t0 = time.time()

    d = start
    while d <= end:
        hd = d.strftime("%Y%m%d")
        d += datetime.timedelta(days=1)
        dst = os.path.join(out, hd + ".json")
        st = days.get(hd) or {}
        if st.get("state") == "done" and os.path.exists(dst):
            continue

        codes = []
        body = None
        for _ in range(1 + RETRIES):
            code, blob = fetcher.get(hd)
            codes.append(code)
            if code == 200 and blob:
                try:
                    body = json.loads(blob.decode("utf-8"))
                    break
                except Exception:
                    codes[-1] = "badjson"
        if body is None:
            days[hd] = {"state": "failed", "codes": codes}
            save_progress(prog_path, prog)
            print(hd, "failed", codes, flush=True)
            continue

        _atomic_write(os.path.join(raw, hd + ".json.gz"), gzip.compress(blob))
        races = to_races(body)
        obj = {"開催日": hd,
               "取得時刻": datetime.datetime.now().isoformat(timespec="seconds"),
               "レース数": len(races), "結果": races}
        _atomic_write(dst, json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8"))
        days[hd] = {"state": "done", "races": len(races),
                    "raw_races": len(body.get("results", []) or []), "tries": len(codes)}
        save_progress(prog_path, prog)
        print(hd, "races", len(races), flush=True)

    done = [k for k, v in days.items() if v.get("state") == "done"]
    failed = sorted(k for k, v in days.items() if v.get("state") == "failed")
    print("done", len(done), "failed", len(failed), "races",
          sum(days[k]["races"] for k in done), "elapsed_sec", int(time.time() - t0))
    if failed:
        print("failed_first5", failed[:5])


if __name__ == "__main__":
    main()
