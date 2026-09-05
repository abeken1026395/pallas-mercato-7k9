#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""選手の出場予定を公式サイトから取得する（ローカル専用）。

1件あたりの所要は実測で中央値9.15秒。ほぼ全部がサーバ側の応答生成待ちで、
接続を使い回しても縮まらない（実測 9.179秒 → 9.146秒）。
そこで「最終取得日が古い順に、制限時間まで取る」形にする。
時間が来たら止め、続きは次回。全1,643名がローリングで一巡する。

  python3 scripts/fetchRacerSchedule.py --minutes 60

出力は data/racerSchedule.json（リポジトリ直下・docs に置かないのでPagesデプロイは起きない）。
"""

import argparse
import html as htmlmod
import http.client
import json
import os
import re
import ssl
import time
from datetime import datetime, timedelta, timezone

HOST = "www.boatrace.jp"
PATH = "/owpc/pc/data/racersearch/profile?toban={}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) fetchRacerSchedule/1.0"
SOURCE = "https://www.boatrace.jp/owpc/pc/data/racersearch/profile?toban=<登番>"

ROSTER = os.path.join("docs", "data", "racerStatsCore.json")
OUTPATH = os.path.join("data", "racerSchedule.json")
SAMPLE = os.path.join("data", "racerScheduleSample.txt")

SLEEP = 1.0
SAVE_EVERY = 20
JST = timezone(timedelta(hours=9))


def now_jst():
    return datetime.now(JST)


def stamp():
    return now_jst().strftime("%Y%m%d%H%M")


def strip_tags(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def label_of(fragment):
    """テキストが無い列は img の alt、それも無ければ class 名を拾う。"""
    text = strip_tags(fragment)
    if text:
        return text
    alt = re.search(r'alt="([^"]*)"', fragment)
    if alt and alt.group(1).strip():
        return alt.group(1).strip()
    cls = re.search(r'class="([^"]*)"', fragment)
    if cls and cls.group(1).strip():
        return cls.group(1).strip()
    return ""


def parse_entry(tbody):
    cells = re.findall(r"<td[^>]*>(.*?)</td>", tbody, re.S)
    if len(cells) < 5:
        return None
    days = re.findall(r"(\d{4})/(\d{2})/(\d{2})", cells[0])
    if not days:
        return None
    start = "".join(days[0])
    end = "".join(days[-1])
    jcd = None
    hit = re.search(r"text_place\d*_(\d{2})\.png", cells[1])
    if hit:
        jcd = int(hit.group(1))
    venue = label_of(cells[1])
    assen = re.search(r"assen\?jcd=(\d+)&(?:amp;)?hd=(\d{8})", cells[4])
    entry = {
        "from": start,
        "to": end,
        "jcd": jcd,
        "venue": venue,
        "grade": label_of(cells[2]),
        "time": label_of(cells[3]),
        "title": strip_tags(cells[4]),
    }
    if assen:
        entry["hd"] = assen.group(2)
    add = label_of(cells[5]) if len(cells) > 5 else ""
    if add:
        entry["add"] = add
    return entry


def parse(page):
    """戻り値 (record, section)。record が None なら異常＝状態を更新しない。"""
    if "title9_mainLabel" not in page:
        if "title12_title" in page:
            return {"status": "missing", "entries": []}, None
        return None, None
    head = re.search(r'title9_mainLabel"[^>]*>\s*出場予定\s*</span>', page)
    if not head:
        return None, None
    start = head.end()
    tail = page.find('<ul class="state1', start)
    section = page[start:tail] if tail > 0 else page[start:]
    if "データがありません" in section:
        return {"status": "none", "entries": []}, section
    bodies = re.findall(r"<tbody[^>]*>(.*?)</tbody>", section, re.S)
    if not bodies:
        return None, section
    entries = []
    for body in bodies:
        entry = parse_entry(body)
        if entry:
            entries.append(entry)
    if not entries:
        return None, section
    return {"status": "ok", "entries": entries}, section


def load_roster():
    with open(ROSTER, encoding="utf-8") as handle:
        data = json.load(handle)
    return [str(int(p["no"])) for p in data["players"]]


def load_out():
    if not os.path.exists(OUTPATH):
        return {}
    with open(OUTPATH, encoding="utf-8") as handle:
        return json.load(handle).get("racers", {})


def save_out(racers):
    rows = []
    for key in sorted(racers, key=int):
        rows.append(
            '  "{}": {}'.format(
                key, json.dumps(racers[key], ensure_ascii=False, separators=(",", ":"))
            )
        )
    text = (
        "{\n"
        '  "schema": "racerSchedule-1",\n'
        '  "出典": "' + SOURCE + '",\n'
        '  "generated": "' + now_jst().strftime("%Y-%m-%d %H:%M JST") + '",\n'
        '  "count": ' + str(len(racers)) + ",\n"
        '  "racers": {\n'
        + ",\n".join(rows)
        + "\n  }\n}\n"
    )
    tmp = OUTPATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp, OUTPATH)


def connect():
    conn = http.client.HTTPSConnection(
        HOST, 443, timeout=40, context=ssl.create_default_context()
    )
    conn.connect()
    return conn


def get(conn, toban):
    conn.request(
        "GET",
        PATH.format(toban),
        headers={"Host": HOST, "User-Agent": UA, "Accept-Encoding": "identity"},
    )
    resp = conn.getresponse()
    body = resp.read()
    return resp.status, body.decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    roster = load_roster()
    racers = load_out()
    order = sorted(roster, key=lambda t: (racers.get(t, {}).get("fetched", ""), int(t)))
    if args.limit:
        order = order[: args.limit]

    deadline = time.time() + args.minutes * 60.0
    conn = None
    done = 0
    failed = 0
    counts = {"ok": 0, "none": 0, "missing": 0}
    sample_written = os.path.exists(SAMPLE)

    print("対象 {} 名 ／ 制限 {} 分 ／ 開始 {}".format(
        len(order), args.minutes, now_jst().strftime("%Y-%m-%d %H:%M JST")), flush=True)

    for toban in order:
        if time.time() >= deadline:
            print("制限時間に達したので停止する", flush=True)
            break
        try:
            if conn is None:
                conn = connect()
            status, page = get(conn, toban)
            if status != 200:
                raise RuntimeError("http {}".format(status))
            record, section = parse(page)
        except Exception as exc:
            failed += 1
            print("{} 失敗 {}".format(toban, exc), flush=True)
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
            conn = None
            time.sleep(SLEEP)
            continue

        if record is None:
            failed += 1
            print("{} 解析できず（状態を更新しない）".format(toban), flush=True)
            if not sample_written and section:
                with open(SAMPLE, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(section[:6000])
                sample_written = True
            time.sleep(SLEEP)
            continue

        record["fetched"] = stamp()
        racers[toban] = record
        counts[record["status"]] += 1
        done += 1
        if not sample_written and record["status"] == "ok" and section:
            with open(SAMPLE, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(section[:6000])
            sample_written = True
        print("{} {} {}件".format(toban, record["status"], len(record["entries"])), flush=True)
        if done % SAVE_EVERY == 0:
            save_out(racers)
        time.sleep(SLEEP)

    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    save_out(racers)

    covered = sum(1 for t in roster if t in racers)
    print("", flush=True)
    print("取得 {} 件（ok {} / none {} / missing {}） 失敗 {} 件".format(
        done, counts["ok"], counts["none"], counts["missing"], failed), flush=True)
    print("名簿 {} 名のうち取得済み {} 名（未取得 {} 名）".format(
        len(roster), covered, len(roster) - covered), flush=True)
    print("終了 {}".format(now_jst().strftime("%Y-%m-%d %H:%M JST")), flush=True)


main()
