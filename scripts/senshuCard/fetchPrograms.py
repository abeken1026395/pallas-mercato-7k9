"""選手カード：優勝戦の判定に使う公式番組（と古い日の結果）を BoatraceOpenAPI から取り、日ごとに小さくして保存する。

使い方: python3 scripts/senshuCard/fetchPrograms.py 開始日 終了日 保存先フォルダ [結果も取る最終日]
- 番組 programs v2：その日の全レースの [場, R, グレード番号, タイトル, 副題, [[艇番, 登番], ...]]
- 結果 results v2（「結果も取る最終日」以前の日だけ）：[場, R, [[登番, 着, コース], ...]]
- 保存：保存先/YYYYMMDD.json.gz = {"pgst": HTTP状態, "pg": [...], "rsst": HTTP状態 or null, "rs": [...]}
- すでにある日は取り直さない（pgst が 200 か 404 のとき）
"""
import concurrent.futures as cf
import datetime as dt
import gzip
import json
import os
import sys
import urllib.error
import urllib.request

PG = "https://raw.githubusercontent.com/BoatraceOpenAPI/programs/gh-pages/docs/v2/{y}/{d}.json"
RS = "https://raw.githubusercontent.com/BoatraceOpenAPI/results/gh-pages/docs/v2/{y}/{d}.json"


def get(url):
    for _ in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
                return 200, json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
            err = e.code
        except Exception as e:  # noqa: BLE001
            err = str(e)[:40]
    return err, None


def one(d, out, rsLast):
    p = os.path.join(out, d + ".json.gz")
    if os.path.exists(p):
        try:
            j = json.load(gzip.open(p))
            if j.get("pgst") in (200, 404) and (d > rsLast or j.get("rsst") in (200, 404)):
                return d, "skip"
        except Exception:  # noqa: BLE001
            pass
    st, j = get(PG.format(y=d[:4], d=d))
    pg = []
    if st == 200:
        for r in j.get("programs", []):
            pg.append([r["race_stadium_number"], r["race_number"], r.get("race_grade_number"), r.get("race_title"), r.get("race_subtitle"),
                       [[b.get("racer_boat_number"), b.get("racer_number")] for b in r.get("boats", [])]])
    rsst, rs = None, []
    if d <= rsLast:
        rsst, k = get(RS.format(y=d[:4], d=d))
        if rsst == 200:
            for r in k.get("results", []):
                rs.append([r["race_stadium_number"], r["race_number"],
                           [[b.get("racer_number"), b.get("racer_place_number"), b.get("racer_course_number")] for b in r.get("boats", [])]])
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump({"pgst": st, "pg": pg, "rsst": rsst, "rs": rs}, f, ensure_ascii=False, separators=(",", ":"))
    return d, st


def main():
    a, b, out = sys.argv[1], sys.argv[2], sys.argv[3]
    rsLast = sys.argv[4] if len(sys.argv) > 4 else "00000000"
    os.makedirs(out, exist_ok=True)
    d0 = dt.date(int(a[:4]), int(a[4:6]), int(a[6:]))
    d1 = dt.date(int(b[:4]), int(b[4:6]), int(b[6:]))
    days = [(d0 + dt.timedelta(n)).strftime("%Y%m%d") for n in range((d1 - d0).days + 1)]
    bad = []
    with cf.ThreadPoolExecutor(16) as ex:
        for i, (d, st) in enumerate(ex.map(lambda x: one(x, out, rsLast), days)):
            if st not in (200, 404, "skip"):
                bad.append((d, st))
            if i % 200 == 0:
                print(i, d, st, flush=True)
    print("days", len(days), "bad", bad[:20], len(bad))


if __name__ == "__main__":
    main()
