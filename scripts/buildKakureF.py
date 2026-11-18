# -*- coding: utf-8 -*-
"""
buildKakureF.py

「隠れF」の選手を出す（2026-11-17 けん「隠れFかどうか知りたい」・A案）。
前期にFを切り、そのF休みをまだ取っていないと見られる選手。出走表のF数は今期の分だけなので、
この選手は出走表で F0 に見える。

判定（推定。公式はF休みの期間を出していない）:
  - 前期 = 今の期の1つ前の期（5/1〜10/31 か 11/1〜4/30）。集計日（JST）から決める。
  - 前期のF = results/ の着コード14。
  - Fの日以降に「30日以上レースに出ていない期間」を F休みとみなす。
    休む日数は1本目のFで30日、2本目以降は1本ごとに60日を足す（F2なら計90日）。
    Fと休みを日付の順に並べ、休みの日数を、まだ休んでいない日数から差し引く。
    同じ日付ではFを先に数える。残りが2日以下なら休み済み。
  - 30日以上の欠場（けが・病気など）も休みとみなすので、隠れFを見落とす側に誤ることがある。
  - 答え合わせ（2026-11-17）: 第三者の推定表（ひまひまデータ3・10/31時点）と、
    隠れFと判定した162人は全員一致（休み前69・休み中93）。

不成立レース:
  複数艇がFして3連単が不成立になったレースは results/ に入らない（2026-10-28 以降は 成立せず に名前だけ残る）。
  前期の範囲で「場ごとのレース番号の抜け」と「成立せず の不成立」を拾い、そのレースだけ
  公式の結果ページを読んで、着が F の登番を足す。読んだ結果は data/kakureFextra.json に残し、読み直さない。
  1回に読むのは EXTRA_MAX 件まで。1件ごとに1.2秒あける。読めなかったレースは次の回に読み直す。

入力:  results/YYYYMMDD.json ／ data/kakureFextra.json ／ 公式 raceresult（抜けたレースだけ）
出力:  docs/data/kakureF.json（出走表 template_racers.html が fetch する）
       data/kakureFextra.json
"""

import glob
import json
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from buildResults import OFFICIAL_URL, OFFICIAL_HEADERS, _section, _text  # noqa: E402

RESULTS_DIR = os.environ.get("KAKUREF_RESULTS", os.path.join(REPO_ROOT, "results"))
OUT_PATH = os.environ.get("KAKUREF_OUT", os.path.join(REPO_ROOT, "docs", "data", "kakureF.json"))
EXTRA_PATH = os.environ.get("KAKUREF_EXTRA", os.path.join(REPO_ROOT, "data", "kakureFextra.json"))
EXTRA_MAX = int(os.environ.get("KAKUREF_EXTRA_MAX", "40"))
NO_FETCH = os.environ.get("KAKUREF_NO_FETCH") == "1"
JST = timezone(timedelta(hours=9))

REST_MIN = 29          # 30日以上レースに出ていない = 間の空白が29日以上
FIRST_DAYS = 30
NEXT_DAYS = 60
SLACK = 2


def d8(s):
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def s8(d):
    return d.strftime("%Y%m%d")


def prev_term(today):
    """集計日を含む期の1つ前の期 (開始, 終了)。"""
    y = today.year
    if 5 <= today.month <= 10:          # 今期 5/1〜10/31 → 前期 前年11/1〜4/30
        return date(y - 1, 11, 1), date(y, 4, 30)
    if today.month >= 11:               # 今期 11/1〜翌4/30 → 前期 5/1〜10/31
        return date(y, 5, 1), date(y, 10, 31)
    return date(y - 1, 5, 1), date(y - 1, 10, 31)   # 1〜4月


def load_extra():
    try:
        with open(EXTRA_PATH, encoding="utf-8") as f:
            j = json.load(f)
        return j if isinstance(j, dict) else {}
    except Exception:
        return {}


def parse_f(page):
    """公式 raceresult の着順表から、着が F の登番を返す。表が読めなければ None。"""
    if page and "<th>着</th>" not in page and "レース中止" in page:
        return []
    if not page or "<th>着</th>" not in page:
        return None
    out = []
    rows = 0
    for body in _section(page, "着").split("<tbody")[1:]:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
        if len(tds) < 3:
            continue
        tou = re.search(r'class="is-fs12">\s*(\d{4})\s*<', tds[2])
        if not tou:
            continue
        rows += 1
        if _text(tds[0])[:1] == "F":
            out.append(tou.group(1))
    return out if rows >= 2 else None


def fetch(hd, jcd, rno):
    url = OFFICIAL_URL.format(rno=rno, jcd=int(jcd), hd=hd)
    req = urllib.request.Request(url, headers=OFFICIAL_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        print("fetch failed", hd, jcd, rno, type(e).__name__)
        return None


def main():
    today = datetime.now(JST).date()
    if os.environ.get("KAKUREF_TODAY"):
        today = d8(os.environ["KAKUREF_TODAY"])
    t0, t1 = prev_term(today)

    race_days = defaultdict(set)     # 登番 -> 出走日
    fs = defaultdict(list)           # 登番 -> [(日, 場)]
    holes = []                       # (日, 場, R) 前期で results/ に無いレース
    files = sorted(glob.glob(os.path.join(RESULTS_DIR, "[0-9]" * 8 + ".json")))
    last = None
    for f in files:
        hd = os.path.basename(f)[:8]
        if hd < s8(t0) or hd > s8(today):
            continue
        try:
            with open(f, encoding="utf-8") as fp:
                j = json.load(fp)
        except Exception:
            print("skip broken", hd)
            continue
        last = max(last or hd, hd)
        in_term = hd <= s8(t1)
        by_v = defaultdict(set)
        for r in j.get("結果") or []:
            jcd = str(r.get("場コード") or "")
            m = re.match(r"(\d+)", str(r.get("レース") or ""))
            if m:
                by_v[jcd].add(int(m.group(1)))
            for b in r.get("艇") or []:
                t = str(b.get("登番") or "")
                if not re.fullmatch(r"\d{4}", t):
                    continue
                race_days[t].add(hd)
                if in_term and str(b.get("着")) == "14":
                    fs[t].append((hd, jcd))
        if not in_term:
            continue
        for v, rs in by_v.items():
            for k in range(1, max(rs) + 1):
                if k not in rs:
                    holes.append((hd, v, k))
        for x in j.get("成立せず") or []:
            if x.get("理由") == "不成立":
                m = re.match(r"(\d+)", str(x.get("レース") or ""))
                if m:
                    holes.append((hd, str(x.get("場コード")), int(m.group(1))))
    if last is None:
        print("no results in range; nothing written")
        return

    # 抜けたレースのFを公式から足す
    extra = load_extra()
    fetched = 0
    for hd, v, k in sorted(set(holes)):
        key = "%s-%s-%d" % (hd, v, k)
        if key not in extra and not NO_FETCH and fetched < EXTRA_MAX:
            if fetched:
                time.sleep(1.2)
            fetched += 1
            got = parse_f(fetch(hd, v, k))
            if got is not None:
                extra[key] = got
        for t in extra.get(key) or []:
            if (hd, v) not in fs[t]:
                fs[t].append((hd, v))
                race_days[t].add(hd)
    left = sum(1 for h in set(holes) if "%s-%s-%d" % h not in extra)

    # 判定
    end = d8(last) + timedelta(days=1)    # 結果がある最後の日の翌日を「今日」とみなす
    out = {}
    for t, fl in fs.items():
        fl = sorted(set(fl))
        f_days = [d8(x[0]) for x in fl]
        days = sorted(d8(x) for x in race_days[t] if x >= fl[0][0])
        if not days:
            days = [f_days[0]]
        gaps = [(a, (b - a).days - 1) for a, b in zip(days, days[1:])]
        gaps.append((days[-1], (end - days[-1]).days - 1))
        ev = [(d, 0, i) for i, d in enumerate(f_days)] + [(a, 1, g) for a, g in gaps if g >= REST_MIN]
        ev.sort(key=lambda e: (e[0], e[1]))
        owe = 0
        need = []      # Fごとの残り日数
        for d, kind, x in ev:
            if kind == 0:
                add = FIRST_DAYS if x == 0 else NEXT_DAYS
                owe += add
                need.append(add)
            else:
                pay = min(owe, x + SLACK)
                owe -= pay
                for i in range(len(need)):
                    p = min(need[i], pay)
                    need[i] -= p
                    pay -= p
        if owe <= SLACK:
            continue
        out[t] = {"F": [[fl[i][0], fl[i][1], 1 if need[i] <= SLACK else 0] for i in range(len(fl))]}

    doc = {
        "集計日": today.strftime("%Y-%m-%d"),
        "前期": [s8(t0), s8(t1)],
        "結果の最終日": last,
        "判定": "Fの日以降に30日以上レースに出ていない期間をF休みとみなす（1本目30日・2本目以降60日）。推定",
        "選手": {k: out[k] for k in sorted(out)},
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    os.makedirs(os.path.dirname(EXTRA_PATH), exist_ok=True)
    with open(EXTRA_PATH, "w", encoding="utf-8") as f:
        json.dump({k: extra[k] for k in sorted(extra)}, f, ensure_ascii=False, indent=0)
        f.write("\n")
    print("kakureF: term %s-%s last %s hidden %d holes %d fetched %d unread %d"
          % (s8(t0), s8(t1), last, len(out), len(set(holes)), fetched, left))


if __name__ == "__main__":
    main()
