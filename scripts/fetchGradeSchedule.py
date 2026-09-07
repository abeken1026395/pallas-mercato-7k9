# -*- coding: utf-8 -*-
"""公式の月間スケジュールから、場×開催日のグレード区分を取得する。

出力: docs/data/gradeSchedule.json
    {"updated": "YYYY-MM-DD HH:MM", "days": {"YYYYMMDD": {"01": {...}}}}

取得元: https://www.boatrace.jp/owpc/pc/race/monthlyschedule?ym=YYYYMM
判定  : td の class="is-gradeColor*"。SG/G1/G2/G3/オールレディース/
        ヴィーナスシリーズ/ルーキーシリーズ/マスターズリーグ/一般 の9区分すべてに
        専用classがあり、inline style の色に頼る必要はない。
注意  : セル内 a の hd= は開催中の節だと当日を指す。開始日には使わない。
        開始日・終了日は列位置と colspan から計算する。
出力  : 当日と翌日の2日分のみ。読者に送る量を増やさないため、全日分は残さない。
        取得に失敗した場合は既存ファイルを書き換えない。
"""
import csv
import datetime
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://www.boatrace.jp/owpc/pc/race/monthlyschedule"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

JST = datetime.timezone(datetime.timedelta(hours=9))
REQ_TIMEOUT = 20
SLEEP_SEC = 1.0
OUT_PATH = os.path.join("docs", "data", "gradeSchedule.json")
CSV_PATH = os.path.join("docs", "racers", "racers_today.csv")
STATS_PATH = os.path.join("docs", "data", "racerStats.json")

GRADE_MAP = {
    "is-gradeColorSG": "SG",
    "is-gradeColorG1": "G1",
    "is-gradeColorG2": "G2",
    "is-gradeColorG3": "G3",
    "is-gradeColorLady": "オールレディース",
    "is-gradeColorVenus": "ヴィーナスシリーズ",
    "is-gradeColorRookie": "ルーキーシリーズ",
    "is-gradeColorTakumi": "マスターズリーグ",
    "is-gradeColorIppan": "一般",
}


def fetch_month(ym):
    """指定年月(YYYYMM)の月間スケジュールHTMLを返す。失敗時 None。"""
    url = "{0}?ym={1}".format(BASE, ym)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT)
    except Exception as e:
        print("取得失敗 {0}: {1}".format(ym, e))
        return None
    if resp.status_code != 200:
        print("取得失敗 {0}: status={1}".format(ym, resp.status_code))
        return None
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def header_dates(table, ym):
    """thead の日付列を date の並びに変換する。

    グリッドは前月末から翌月初をまたぐ（9月ページは 8/28 から 10/4）。
    先頭が1日でなければ前月始まり。数字が前の値より小さくなったら月を1つ進める。
    """
    thead = table.find("thead")
    if thead is None:
        return []
    ths = thead.find_all("th")
    nums = []
    for th in ths[1:]:
        m = re.search(r"\d+", th.get_text(" ", strip=True))
        if m:
            nums.append(int(m.group()))
    if not nums:
        return []
    year = int(ym[:4])
    month = int(ym[4:])
    if nums[0] != 1:
        if month == 1:
            year, month = year - 1, 12
        else:
            month -= 1
    out = []
    prev = 0
    for n in nums:
        if prev and n < prev:
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
        try:
            out.append(datetime.date(year, month, n))
        except ValueError:
            out.append(None)
        prev = n
    return out


def parse_sections(html, ym):
    """1か月ぶんのHTMLから節の一覧を返す。"""
    soup = BeautifulSoup(html, "html.parser")
    sections = []
    for table in soup.select("div.table1 table"):
        dates = header_dates(table, ym)
        if not dates:
            continue
        rows = []
        for tbody in table.find_all("tbody"):
            rows.extend(tbody.find_all("tr"))
        if not rows:
            continue
        for tr in rows:
            th = tr.find("th")
            if th is None:
                continue
            a = th.find("a", href=True)
            m = re.search(r"jcd=(\d{2})", a["href"]) if a else None
            if not m:
                continue
            jcd = m.group(1)
            col = 0
            for td in tr.find_all("td", recursive=False):
                try:
                    span = int(td.get("colspan"))
                except (TypeError, ValueError):
                    span = 1
                hit = None
                for c in (td.get("class") or []):
                    if c in GRADE_MAP:
                        hit = c
                        break
                if hit and col < len(dates):
                    start = dates[col]
                    end = dates[min(col + span - 1, len(dates) - 1)]
                    link = td.find("a")
                    name = link.get_text(" ", strip=True) if link else td.get_text(" ", strip=True)
                    if start and end:
                        sections.append({
                            "jcd": jcd,
                            "区分": GRADE_MAP[hit],
                            "節名": name,
                            "開始日": start.strftime("%Y%m%d"),
                            "終了日": end.strftime("%Y%m%d"),
                        })
                col += span
    return sections


def build_days(sections, targets):
    """節の一覧を、対象日(YYYYMMDD の list)ごとの 場コード→情報 に展開する。

    グリッドの左右端で切れた節は、前後の月ページで断片として現れる。
    同じ場・同じ日に複数の断片が来たら、開始日は早い方、終了日は遅い方を採り、
    節名は空でない方を残す（切れた側は節名の a が無いことがあるため）。
    """
    days = {}
    for hd in targets:
        days[hd] = {}
    for s in sections:
        try:
            d0 = datetime.datetime.strptime(s["開始日"], "%Y%m%d").date()
            d1 = datetime.datetime.strptime(s["終了日"], "%Y%m%d").date()
        except ValueError:
            continue
        if d1 < d0:
            continue
        d = d0
        while d <= d1:
            hd = d.strftime("%Y%m%d")
            if hd in days:
                cur = days[hd].get(s["jcd"])
                if cur is None:
                    days[hd][s["jcd"]] = {
                        "区分": s["区分"],
                        "節名": s["節名"],
                        "開始日": s["開始日"],
                        "終了日": s["終了日"],
                    }
                else:
                    if s["開始日"] < cur["開始日"]:
                        cur["開始日"] = s["開始日"]
                    if s["終了日"] > cur["終了日"]:
                        cur["終了日"] = s["終了日"]
                    if not cur["節名"] and s["節名"]:
                        cur["節名"] = s["節名"]
            d += datetime.timedelta(days=1)
    return days


def load_female_map():
    """登録番号 -> 女子かどうか。読めなければ空の dict。"""
    try:
        with open(STATS_PATH, encoding="utf-8") as f:
            players = json.load(f).get("players", [])
    except Exception as e:
        print("racerStats.json を読めない: {0}".format(e))
        return {}
    out = {}
    for p in players:
        no = str(p.get("no", "")).strip()
        if no:
            out[no] = bool(p.get("female"))
    return out


def load_entries():
    """(開催日, 場コード) -> 登録番号の集合。読めなければ空の dict。"""
    out = {}
    try:
        with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                hd = (row.get("開催日") or "").strip()
                jcd = (row.get("場コード") or "").strip()
                no = (row.get("登録番号") or "").strip()
                if hd and jcd and no:
                    out.setdefault((hd, jcd), set()).add(no)
    except Exception as e:
        print("racers_today.csv を読めない: {0}".format(e))
    return out


def annotate_female(days):
    """その場・その日の出走選手が全員女子なら レディース=true を立てる。

    判定は延べでなく実人数（登録番号の集合）。選手マスタに載っていない選手が
    1人でもいる場合は判定しない。分母を残すため 女子・出走 も併記する。
    公式の区分では女子のSG・G1が Lady にならないため、区分ではなく出走選手で見る。
    """
    fmap = load_female_map()
    entries = load_entries()
    if not fmap or not entries:
        print("女子判定の入力が揃わないため付与しない")
        return
    for hd in days:
        for jcd, info in days[hd].items():
            ids = entries.get((hd, jcd))
            if not ids:
                continue
            if any(i not in fmap for i in ids):
                continue
            n = len(ids)
            f = sum(1 for i in ids if fmap[i])
            info["女子"] = f
            info["出走"] = n
            info["レディース"] = (f == n)


def target_months(today, tomorrow):
    """取得する年月(YYYYMM)を返す。前月・当月・翌日の月の順で重複を除く。

    月初は当月ページの左端で節が切れるため、前月ページで開始日を補う。
    """
    prev = (today.replace(day=1) - datetime.timedelta(days=1))
    yms = []
    for d in (prev, today, tomorrow):
        ym = d.strftime("%Y%m")
        if ym not in yms:
            yms.append(ym)
    return yms


def main():
    today = datetime.datetime.now(JST).date()
    tomorrow = today + datetime.timedelta(days=1)
    targets = [today.strftime("%Y%m%d"), tomorrow.strftime("%Y%m%d")]

    sections = []
    ok = 0
    for i, ym in enumerate(target_months(today, tomorrow)):
        if i:
            time.sleep(SLEEP_SEC)
        html = fetch_month(ym)
        if html is None:
            continue
        got = parse_sections(html, ym)
        print("{0}: {1}節".format(ym, len(got)))
        sections.extend(got)
        ok += 1

    if ok == 0 or not sections:
        print("取得0件のため gradeSchedule.json は更新しない")
        return

    days = build_days(sections, targets)
    annotate_female(days)
    out = {
        "updated": datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "days": days,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    for hd in targets:
        print("{0}: {1}場".format(hd, len(days.get(hd, {}))))
    print("保存: {0}".format(OUT_PATH))


if __name__ == "__main__":
    main()
