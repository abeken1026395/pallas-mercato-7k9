#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""選手の出場予定を公式サイトから取得する（ローカル専用）。

1件あたりの所要は実測で中央値9.15秒。ほぼ全部がサーバ側の応答生成待ちで、
接続を使い回しても縮まらない（実測 9.179秒 → 9.146秒）。
ただし IP 単位の直列化は無く、8並列にしても実時間は1件分と同じ（実測 10.38秒）。
そこで既定8並列にしたうえで「最終取得日が古い順に、制限時間まで取る」形にする。
時間が来たら止め、続きは次回。全1,643名がローリングで一巡する。

  python3 scripts/fetchRacerSchedule.py --minutes 60
  python3 scripts/fetchRacerSchedule.py --minutes 60 --workers 4

出力は data/racerSchedule.json（リポジトリ直下・docs に置かないのでPagesデプロイは起きない）。
"""

import argparse
import html as htmlmod
import http.client
import json
import os
import re
import ssl
import threading
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
WORKERS = 8
JST = timezone(timedelta(hours=9))


def now_jst():
    return datetime.now(JST)


def stamp():
    return now_jst().strftime("%Y%m%d%H%M")


def strip_tags(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


LAYOUT = re.compile(r"^(is-p\d+-\d+|is-align[LRC]|is-fBold|is-w\d+)$")


def class_tokens(cell):
    """td の class から、レイアウト用でない is- トークンだけを拾う。

    グレードと開催時間帯は td の中身が空で、class 名だけで表現されている。
    例 <td class="is-p10-5 is-ippan "></td>
    """
    head = re.match(r"<td([^>]*)>", cell, re.S)
    if not head:
        return []
    found = re.search(r'class="([^"]*)"', head.group(1))
    if not found:
        return []
    return [t for t in found.group(1).split()
            if t.startswith("is-") and not LAYOUT.match(t)]


def label_of(cell):
    """テキストが無い列は img の alt、それも無ければ class 名を拾う。"""
    text = strip_tags(cell)
    if text:
        return text
    alt = re.search(r'alt="([^"]*)"', cell)
    if alt and alt.group(1).strip():
        return alt.group(1).strip()
    return " ".join(class_tokens(cell))


def parse_entry(tbody):
    cells = re.findall(r"(<td[^>]*>.*?</td>)", tbody, re.S)
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


def run_worker(order, cursor, deadline, state, lock):
    """接続を1本持ち、担当分を順に取る。1件あたりの待ちはサーバ側の応答生成で、
    IP単位の直列化は無いので（実測 8並列で実時間が1件分と同じ）そのまま重ねられる。
    """
    conn = None
    while True:
        with lock:
            if time.time() >= deadline:
                if cursor[0] < len(order) and not state["stopped"]:
                    state["stopped"] = True
                    print("制限時間に達したので停止する", flush=True)
                break
            if cursor[0] >= len(order):
                break
            toban = order[cursor[0]]
            cursor[0] += 1
        try:
            if conn is None:
                conn = connect()
            status, page = get(conn, toban)
            if status != 200:
                raise RuntimeError("http {}".format(status))
            record, section = parse(page)
        except Exception as exc:
            with lock:
                state["failed"] += 1
                print("{} 失敗 {}".format(toban, exc), flush=True)
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
            conn = None
            time.sleep(SLEEP)
            continue

        with lock:
            if record is None:
                state["failed"] += 1
                print("{} 解析できず（状態を更新しない）".format(toban), flush=True)
                if not state["sample"] and section:
                    with open(SAMPLE, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write(section[:6000])
                    state["sample"] = True
            else:
                record["fetched"] = stamp()
                state["racers"][toban] = record
                state["counts"][record["status"]] += 1
                state["done"] += 1
                if not state["sample"] and record["status"] == "ok" and section:
                    with open(SAMPLE, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write(section[:6000])
                    state["sample"] = True
                print("{} {} {}件".format(
                    toban, record["status"], len(record["entries"])), flush=True)
                if state["done"] % SAVE_EVERY == 0:
                    save_out(state["racers"])
        time.sleep(SLEEP)

    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()

    roster = load_roster()
    racers = load_out()
    order = sorted(roster, key=lambda t: (racers.get(t, {}).get("fetched", ""), int(t)))
    if args.limit:
        order = order[: args.limit]

    deadline = time.time() + args.minutes * 60.0
    workers = max(1, args.workers)
    cursor = [0]
    lock = threading.Lock()
    state = {
        "racers": racers,
        "done": 0,
        "failed": 0,
        "counts": {"ok": 0, "none": 0, "missing": 0},
        "sample": os.path.exists(SAMPLE),
        "stopped": False,
    }

    print("対象 {} 名 ／ 制限 {} 分 ／ 並列 {} ／ 開始 {}".format(
        len(order), args.minutes, workers,
        now_jst().strftime("%Y-%m-%d %H:%M JST")), flush=True)

    threads = [
        threading.Thread(
            target=run_worker, args=(order, cursor, deadline, state, lock)
        )
        for _ in range(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with lock:
        save_out(state["racers"])

    done = state["done"]
    failed = state["failed"]
    counts = state["counts"]
    covered = sum(1 for t in roster if t in racers)
    print("", flush=True)
    print("取得 {} 件（ok {} / none {} / missing {}） 失敗 {} 件".format(
        done, counts["ok"], counts["none"], counts["missing"], failed), flush=True)
    print("名簿 {} 名のうち取得済み {} 名（未取得 {} 名）".format(
        len(roster), covered, len(roster) - covered), flush=True)
    print("終了 {}".format(now_jst().strftime("%Y-%m-%d %H:%M JST")), flush=True)


main()
