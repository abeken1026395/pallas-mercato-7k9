# -*- coding: utf-8 -*-
"""syncStadiumIn1.py — 24場ページ（docs/stadium/index.html・手書き）の1コース1着率を、24場番付と同じ数字にそろえる

使い方  python3 scripts/syncStadiumIn1.py
入力    analysis/venueRank/venueRankLive.json（updateVenueRank.py の出力）
書くもの docs/stadium/index.html の次の3か所だけ。ほかの文字は1字も変えない
  1. window.__D の各場の "in1"（数字だけ差し替え。数字の後ろの注記は、数字や期間を含まないもの「(企画ゲタ大)」だけ残す）
  2. 一覧の上の注記「1コース1着率は進入コース基準。期間・全24場◯艇（出典: …）」
  3. meta description と og:description の同じ文
どれか1つでも見つからなければ何も書かずに止まる（終了コード1）。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "analysis", "venueRank", "venueRankLive.json")
PAGE = os.path.join(ROOT, "docs", "stadium", "index.html")
HEAD = "<script>window.__D = "
TAIL = ";</script>"


def stop(msg):
    print("STOP: " + msg)
    sys.exit(1)


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    c1 = d["指標"]["c1"]["場"]
    p0, p1 = d["期間"]
    fr = "%s-%s-%s" % (p0[:4], p0[4:6], p0[6:])
    to = "%s-%s-%s" % (p1[:4], p1[4:6], p1[6:])
    n = sum(c1[v][1] for v in c1)
    raw = open(PAGE, encoding="utf-8").read()
    i = raw.find(HEAD)
    if i < 0:
        stop("window.__D が無い")
    j = raw.find(TAIL, i)
    seg = raw[i + len(HEAD):j]
    D = json.loads(seg)
    if json.dumps(D, ensure_ascii=False) != seg:
        stop("window.__D を書き戻すと形が変わる（手で直された可能性）")
    changed = 0
    for s in D["stadiums"]:
        v = s["code"]
        if v not in c1 or c1[v][1] == 0:
            stop("場 %s の数字が無い" % v)
        val = "%.1f%%" % (100.0 * c1[v][0] / c1[v][1])
        m = re.match(r"^\s*[\d.]+%(.*)$", s["in1"])
        if not m:
            stop("場 %s の in1 が数字で始まらない: %s" % (v, s["in1"]))
        note = m.group(1)
        if re.search(r"\d", note):
            note = ""
        new = val + note
        if new != s["in1"]:
            changed += 1
        s["in1"] = new
    out = raw[:i + len(HEAD)] + json.dumps(D, ensure_ascii=False) + raw[j:]
    cap_re = r"1コース1着率は進入コース基準。\d{4}-\d{2}-\d{2}〜\d{4}-\d{2}-\d{2}・全24場[\d,]+艇（出典: [^）]*）"
    cap_new = "1コース1着率は進入コース基準。%s〜%s・全24場%s艇（出典: 公式競走成績・24場番付と同じ数字）" % (fr, to, format(n, ","))
    out, k1 = re.subn(cap_re, cap_new, out)
    desc_re = r"1コース1着率は進入コース基準で、\d{4}-\d{2}-\d{2}〜\d{4}-\d{2}-\d{2}の全24場[\d,]+艇の公式競走成績から数えています。"
    desc_new = "1コース1着率は進入コース基準で、%s〜%sの全24場%s艇の公式競走成績から数えています。" % (fr, to, format(n, ","))
    out, k2 = re.subn(desc_re, desc_new, out)
    if k1 != 1 or k2 != 2:
        stop("注記 %d 件・説明文 %d 件（期待は 1 件・2 件）" % (k1, k2))
    if out != raw:
        with open(PAGE, "w", encoding="utf-8", newline="") as f:
            f.write(out)
    print("in1 変更", changed, "場／期間", fr, to, "／", n, "艇／書いた" if out != raw else "／変化なし")


if __name__ == "__main__":
    main()
