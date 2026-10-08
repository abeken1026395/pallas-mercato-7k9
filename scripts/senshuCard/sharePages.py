#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""選手カードの共有用ページとサムネ画像を作る（LINE・X に貼ったとき選手ごとに出すため）。

LINE・X はページの中のプログラムを読まないので、card.html?toban= では「選手カード」としか出ない。
選手ごとに、OGP だけを持つ小さな入口ページを置き、開いたらすぐ card.html?toban= に移す。

  docs/players/card/s/<登番>.html  … 入口ページ（noindex。すぐ選手カードへ移る）
  docs/players/card/og/<登番>.png  … サムネ（1200x630。名札だけ＝登番・名前・支部・級・二つ名。成績の数字は入れない）

中身が同じなら書き換えない（毎週の更新でファイルが動くのは、級・名前・二つ名が変わった人だけ）。
引退などで一覧から消えた人のファイルは消さない（送ったリンクを壊さない）。
字形は kgOutline.json（キルゴU）だけで描く。書体ファイルは使わない。

使い方: python3 scripts/senshuCard/sharePages.py docs/players/card
"""
import glob
import hashlib
import html
import io
import json
import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw

SITE = "https://abeken1026395.github.io/pallas-mercato-7k9/players/card"
W, H, SS = 1200, 630, 2          # 出力の大きさ／描くときの倍率（縁をなめらかにするため）
BG = (13, 13, 13)
RED = (255, 42, 42)
WHITE = (255, 255, 255)
GRAY = (189, 189, 189)
PLATE = (247, 247, 243)
INK = (18, 18, 18)

K = None


def glyphs(s):
    return [(ch, K["g"].get(ch)) for ch in s]


def rings(d):
    out = []
    for part in re.findall(r"M[^MZ]*Z", d):
        nums = list(map(float, re.findall(r"-?\d+(?:\.\d+)?", part)))
        pts = list(zip(nums[0::2], nums[1::2]))
        if len(pts) >= 3:
            out.append(pts)
    return out


def text_w(s, px, ls=0):
    """字の並びの幅（px）。ls は字間（字形の単位。負で詰める）"""
    x = 0
    for ch, g in glyphs(s):
        x += (g[0] if g else 300) + ls
    return max(0, x - ls) * px / 940


def draw_text(img, s, x, y, px, color, ls=0):
    """左上 (x, y) から、高さ px で s を描く。y は字形の 40（上端）に合わせる"""
    sc = px / 940
    cx = 0
    for ch, g in glyphs(s):
        if g and g[1]:
            rs = [[(x + (cx + a) * sc, y + (b - 40) * sc) for a, b in r] for r in rings(g[1])]
            xs = [p[0] for r in rs for p in r]
            ys = [p[1] for r in rs for p in r]
            ox, oy = int(min(xs)) - 2, int(min(ys)) - 2
            size = (int(max(xs)) - ox + 3, int(max(ys)) - oy + 3)
            # 外形と穴を偶奇で塗る（輪ごとに塗って重なりを反転）
            m = Image.new("L", size, 0)
            for r in rs:
                tmp = Image.new("L", size, 0)
                ImageDraw.Draw(tmp).polygon([(a - ox, b - oy) for a, b in r], fill=255)
                m = ImageChops.logical_xor(m.convert("1"), tmp.convert("1")).convert("L")
            img.paste(color, (ox, oy), m)
        cx += (g[0] if g else 300) + ls
    return max(0, cx - ls) * sc


def plate_image(p, toban):
    S = SS
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)

    # 1段目：登番の白札・支部・級（まとめて中央）
    lab_px, no_px, br_px, gr_px = 26 * S, 54 * S, 36 * S, 40 * S
    pad = 20 * S
    no_w = max(text_w("登番", lab_px), text_w(toban, no_px))
    box_w, box_h = no_w + pad * 2, lab_px + no_px + pad * 2 + 6 * S
    br = (p.get("branch") or "") + "支部"
    br_w = text_w(br, br_px)
    gr = p.get("rank") or ""
    gr_w = text_w(gr, gr_px) + 24 * S
    gap = 36 * S
    total = box_w + gap + br_w + gap + gr_w
    x0, y0 = (W * S - total) / 2, 36 * S
    d.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=PLATE)
    draw_text(img, "登番", x0 + (box_w - text_w("登番", lab_px)) / 2, y0 + pad, lab_px, INK)
    draw_text(img, toban, x0 + (box_w - text_w(toban, no_px)) / 2, y0 + pad + lab_px + 6 * S, no_px, INK)
    cy = y0 + box_h / 2
    draw_text(img, br, x0 + box_w + gap, cy - br_px / 2, br_px, GRAY)
    gx = x0 + box_w + gap + br_w + gap
    if gr:
        d.rectangle([gx, cy - gr_px / 2 - 12 * S, gx + gr_w, cy + gr_px / 2 + 12 * S], outline=WHITE, width=5 * S)
        draw_text(img, gr, gx + 12 * S, cy - gr_px / 2, gr_px, WHITE)

    # 2段目：ふりがな＋名前（姓・名に分けて、間を空ける）
    np_ = p.get("np") or [p["name"]]
    kp = p.get("kp") or [""] * len(np_)
    nm_px = 170 * S
    ls = -10
    part_gap = 0.28
    def name_w(px):
        return sum(text_w(n, px, ls) for n in np_) + px * part_gap * (len(np_) - 1)
    while name_w(nm_px) > 1100 * S and nm_px > 80 * S:
        nm_px -= 4 * S
    rb_px = max(30 * S, round(nm_px * 0.24))
    ny = y0 + box_h + 30 * S + rb_px + 10 * S
    nx = (W * S - name_w(nm_px)) / 2
    for i, n in enumerate(np_):
        w = text_w(n, nm_px, ls)
        k = kp[i] if i < len(kp) else ""
        if k:
            kw = text_w(k, rb_px)
            if kw > w:
                kpx = rb_px * w / kw
                draw_text(img, k, nx, ny - rb_px - 10 * S + (rb_px - kpx), kpx, RED)
            else:
                draw_text(img, k, nx + (w - kw) / 2, ny - rb_px - 10 * S, rb_px, RED)
        draw_text(img, n, nx, ny, nm_px, RED, ls)
        nx += w + nm_px * part_gap

    # 3段目：二つ名（あれば）
    tag = (p.get("tag") or "").strip()
    by = ny + nm_px + 22 * S
    if tag:
        tg_px = 38 * S
        while text_w(tag, tg_px) > 1080 * S and tg_px > 20 * S:
            tg_px -= 2 * S
        tw = text_w(tag, tg_px)
        tx = (W * S - tw) / 2
        d.rectangle([tx - 16 * S, by, tx + tw + 16 * S, by + tg_px + 20 * S], fill=(226, 53, 59))
        draw_text(img, tag, tx, by + 10 * S, tg_px, WHITE)

    # 足：サイト名と赤い線
    ft = "データ攻め・選手カード"
    ft_px = 26 * S
    draw_text(img, ft, (W * S - text_w(ft, ft_px)) / 2, H * S - 18 * S - 22 * S - ft_px, ft_px, GRAY)
    d.rectangle([0, H * S - 18 * S, W * S, H * S], fill=(226, 53, 59))

    img = img.resize((W, H), Image.LANCZOS)
    # 32色に減らして軽くする（1枚 約25KB。フルカラーだと約80KB）
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
    global K
    root = sys.argv[1] if len(sys.argv) > 1 else "docs/players/card"
    K = json.load(open(os.path.join(root, "kgOutline.json"), encoding="utf-8"))
    P = {}
    for f in sorted(glob.glob(os.path.join(root, "p", "*.json"))):
        P.update(json.load(open(f, encoding="utf-8")))
    ix = json.load(open(os.path.join(root, "index.json"), encoding="utf-8"))
    os.makedirs(os.path.join(root, "s"), exist_ok=True)
    os.makedirs(os.path.join(root, "og"), exist_ok=True)
    lack = set()
    n_img = n_page = 0
    for toban in sorted(ix, key=int):
        p = P.get(toban)
        if not p:
            continue
        for s in [p["name"], p.get("tag") or "", p.get("branch") or "", p.get("rank") or "", "".join(p.get("kp") or []), toban]:
            lack |= {c for c in s if c != " " and not (K["g"].get(c) or [0, ""])[1]}
        png = plate_image(p, toban)
        ver = hashlib.sha256(png).hexdigest()[:8]
        n_img += write_if_changed(os.path.join(root, "og", toban + ".png"), png)
        n_page += write_if_changed(os.path.join(root, "s", toban + ".html"), page_html(p, toban, ver).encode("utf-8"))
    print(f"選手 {len(ix)} 人／書き換え 画像 {n_img}・ページ {n_page}")
    if lack:
        # 字形の無い字は空白で描かれる。止めずに知らせる（名前が欠けた画像を出さないよう、ここで失敗させる）
        print("字形の無い字: " + "".join(sorted(lack)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
