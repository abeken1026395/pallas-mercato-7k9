"""本日の中止レースを公式「本日のレース一覧」から取り、docs/data/chushiToday.json に書く。

出典: https://www.boatrace.jp/owpc/pc/race/index?hd=YYYYMMDD
中止は出走表（racelist）には書かれない。締切予定時刻の行も実在しない値に変わるため、
時刻からは判定できない。場ごとの欄 td.is-attentionColor1 の文言だけを読む。
  「中止順延」「中止」     … 全レース中止（から=1）
  「5R以降中止順延」等     … その場の5R以降が中止（から=5）

書き出し: {"開催日", "取得時刻", "出典", "中止": {場コード: {"から": int, "表記": str}}}
中止が無い日は "中止": {}。
取得に失敗した・場の欄を1つも読めなかったときは何も書かない（前回の値を残す）。
表示側は 開催日 が当日と一致するときだけ使うので、古い値が残っても誤表示しない。
開催日と中止の中身が前回と同じなら書き換えない（取得時刻だけのコミットを出さない）。
"""
import argparse
import datetime
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

JST = datetime.timezone(datetime.timedelta(hours=9))
OUT = os.path.join("docs", "data", "chushiToday.json")
URL = "https://www.boatrace.jp/owpc/pc/race/index?hd={hd}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}
_FW = str.maketrans("０１２３４５６７８９ＲＲ", "0123456789RR")


def parse(html):
    """(読めた場の数, {場コード: {"から": int, "表記": str}}) を返す。"""
    soup = BeautifulSoup(html, "html.parser")
    seen = 0
    out = {}
    for tb in soup.find_all("tbody"):
        a = tb.find("a", href=re.compile(r"raceindex\?jcd=\d{2}"))
        if not a:
            continue
        jcd = re.search(r"jcd=(\d{2})", a["href"]).group(1)
        seen += 1
        for td in tb.find_all("td", class_="is-attentionColor1"):
            t = re.sub(r"\s+", "", td.get_text("", strip=True)).translate(_FW)
            if "中止" not in t:
                continue
            m = re.search(r"(\d{1,2})R以降", t)
            out[jcd] = {"から": int(m.group(1)) if m else 1, "表記": t}
            break
    return seen, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="保存済みHTMLを読む（検証用）")
    ap.add_argument("--hd", help="開催日 YYYYMMDD（省略時は当日JST）")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    now = datetime.datetime.now(JST)
    hd = args.hd or now.strftime("%Y%m%d")
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            html = f.read()
    else:
        try:
            r = requests.get(URL.format(hd=hd), headers=HEADERS, timeout=30)
        except Exception as e:
            print("取得失敗（書かない）:", e)
            return 0
        if r.status_code != 200:
            print("取得失敗（書かない）: HTTP", r.status_code)
            return 0
        r.encoding = "utf-8"
        html = r.text

    seen, chushi = parse(html)
    if seen == 0:
        print("場の欄を1つも読めない（書かない）。ページ構造の変更を疑う")
        return 0

    try:
        with open(args.out, encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        prev = {}
    if prev.get("開催日") == hd and prev.get("中止") == chushi:
        print("変化なし（書かない）: 場{}・中止{}".format(seen, len(chushi)))
        return 0

    doc = {
        "開催日": hd,
        "取得時刻": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "出典": "boatrace.jp 本日のレース一覧",
        "中止": chushi,
    }
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("書き出し: 場{}・中止{}".format(seen, len(chushi)), json.dumps(chushi, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
