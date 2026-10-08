#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""選手カードの共有用ページとサムネ画像を作る（LINE・X に貼ったとき選手ごとに出すため）。

LINE・X はページの中のプログラムを読まないので、card.html?toban= では「選手カード」としか出ない。
選手ごとに、OGP だけを持つ小さな入口ページを置き、開いたらすぐ card.html?toban= に移す。

  docs/players/card/s/<登番>.html  … 入口ページ（noindex。すぐ選手カードへ移る）
  docs/players/card/og/<登番>.png  … サムネ（1200x630。カードの名札そのもの）

サムネは ogRender.mjs が card.html の名札の描き方（scPlate）でそのまま描く。ここでは描かない。
作り直すのは「名札に使う値・名札の描き方・使う字形」のどれかが変わった人だけ
（data/senshuCard/ogKeys.json に人ごとの鍵を持つ。Chromium の版が変わっても全員は作り直さない）。
引退などで一覧から消えた人のファイルは消さない（送ったリンクを壊さない）。

使い方: python3 scripts/senshuCard/sharePages.py docs/players/card [--all]
  --all … 鍵に関係なく全員を作り直す
"""
import glob
import hashlib
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image

SITE = "https://abeken1026395.github.io/pallas-mercato-7k9/players/card"
W, H = 1200, 630
KEYS = "data/senshuCard/ogKeys.json"
HERE = os.path.dirname(os.path.abspath(__file__))


def plate_source(card_html):
    """名札の描き方の正本（card.html の const SC= から const CH= の手前まで）。ここが変われば全員作り直す"""
    s = open(card_html, encoding="utf-8").read()
    m = re.search(r"const SC=\{P2:\{\}\};.*?(?=\nconst CH=)", s, re.S)
    if not m:
        raise SystemExit("card.html に名札の描き方（const SC= … const CH=）が見つからない")
    return m.group(0)


def plate_input(p, toban):
    return {"toban": toban, "name": p["name"], "np": p.get("np"), "kp": p.get("kp"),
            "rank": p.get("rank"), "tag": p.get("tag") or ""}


def key_of(inp, src_hash, K):
    chars = sorted(set("".join([inp["toban"], "登番", inp["name"], inp["tag"], "".join(inp.get("np") or []), "".join(inp.get("kp") or [])])))
    gl = {c: K["g"].get(c) for c in chars}
    blob = json.dumps([inp, src_hash, gl, ogRenderHash()], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


_rh = None
def ogRenderHash():
    global _rh
    if _rh is None:
        _rh = hashlib.sha256(open(os.path.join(HERE, "ogRender.mjs"), "rb").read()).hexdigest()[:16]
    return _rh


def shrink(raw_png):
    """32色に減らして軽くする（1枚 約20KB。そのままだと約100KB）"""
    img = Image.open(io.BytesIO(raw_png)).convert("RGB")
    img = img.quantize(32, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def page_html(p, toban, ver):
    name = p["name"]
    kana = " ".join(k for k in (p.get("kp") or []) if k)
    br = (p.get("branch") or "") + "支部"
    gr = p.get("rank") or ""
    title = f"{name}（{kana}）｜選手カード" if kana else f"{name}｜選手カード"
    desc = f"{br}・{gr}・登番{toban}。全選手の中で、この選手はどこにいるか。1枚で、分母つきで。"
    to = f"../../card.html?toban={toban}"
    e = html.escape
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{e(name)}（{toban}）｜選手カード｜データ攻め</title>
<meta name="description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="データ攻め">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE}/s/{toban}.html">
<meta property="og:image" content="{SITE}/og/{toban}.png?v={ver}">
<meta property="og:image:width" content="{W}">
<meta property="og:image:height" content="{H}">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{SITE.rsplit('/', 1)[0]}/card.html?toban={toban}">
<style>body{{margin:0;font-family:sans-serif;background:#fff;color:#333;display:flex;align-items:center;justify-content:center;min-height:100vh}}a{{color:#1a5fb4}}</style>
</head>
<body>
<p><a href="{to}">{e(name)}の選手カードを開く</a></p>
<script>location.replace({json.dumps(to)});</script>
</body>
</html>
"""


def write_if_changed(path, data):
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    with open(path, "wb") as f:
        f.write(data)
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--all" in sys.argv
    root = args[0] if args else "docs/players/card"
    docs = os.path.dirname(os.path.dirname(os.path.abspath(root)))
    K = json.load(open(os.path.join(root, "kgOutline.json"), encoding="utf-8"))
    P = {}
    for f in sorted(glob.glob(os.path.join(root, "p", "*.json"))):
        P.update(json.load(open(f, encoding="utf-8")))
    ix = json.load(open(os.path.join(root, "index.json"), encoding="utf-8"))
    src_hash = hashlib.sha256(plate_source(os.path.join(docs, "players", "card.html")).encode("utf-8")).hexdigest()[:16]
    keys = json.load(open(KEYS, encoding="utf-8")) if os.path.exists(KEYS) else {}
    os.makedirs(os.path.join(root, "s"), exist_ok=True)
    os.makedirs(os.path.join(root, "og"), exist_ok=True)

    lack, todo, newkeys = set(), [], {}
    for toban in sorted(ix, key=int):
        p = P.get(toban)
        if not p:
            continue
        inp = plate_input(p, toban)
        for s in [inp["name"], inp["tag"], "".join(inp["kp"] or []), toban]:
            lack |= {c for c in s if c != " " and not (K["g"].get(c) or [0, ""])[1]}
        k = key_of(inp, src_hash, K)
        newkeys[toban] = k
        if force or keys.get(toban) != k or not os.path.exists(os.path.join(root, "og", toban + ".png")):
            todo.append(toban)
    if lack:
        # 字形の無い字は空白で描かれる。名前が欠けたサムネを出さないよう、ここで止める
        print("字形の無い字: " + "".join(sorted(lack)))
        return 1

    n_img = 0
    if todo:
        with tempfile.TemporaryDirectory() as tmp:
            lst = os.path.join(tmp, "list.txt")
            open(lst, "w").write("\n".join(todo))
            out = os.path.join(tmp, "png")
            r = subprocess.run(["node", os.path.join(HERE, "ogRender.mjs"), docs, lst, out])
            if r.returncode != 0:
                print("サムネを描けなかった（ogRender.mjs rc=%d）" % r.returncode)
                return 1
            for toban in todo:
                raw = open(os.path.join(out, toban + ".png"), "rb").read()
                n_img += write_if_changed(os.path.join(root, "og", toban + ".png"), shrink(raw))
                keys[toban] = newkeys[toban]

    n_page = 0
    for toban in sorted(newkeys, key=int):
        png = open(os.path.join(root, "og", toban + ".png"), "rb").read()
        ver = hashlib.sha256(png).hexdigest()[:8]
        n_page += write_if_changed(os.path.join(root, "s", toban + ".html"), page_html(P[toban], toban, ver).encode("utf-8"))

    os.makedirs(os.path.dirname(KEYS), exist_ok=True)
    write_if_changed(KEYS, (json.dumps(dict(sorted(keys.items(), key=lambda x: int(x[0]))), ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    print(f"選手 {len(ix)} 人／描き直し {len(todo)} 人／書き換え 画像 {n_img}・ページ {n_page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
