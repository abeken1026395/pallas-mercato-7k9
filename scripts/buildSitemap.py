#!/usr/bin/env python3
"""
docs/sitemap.xml を生成する（siteReachPlan20260911 V3）。

- 検索に開いているページ（2026-09-11 裁定の C案）の URL だけを列挙する。
  検証記事は /kensho/ ハブのリンクから拾うので、公開した回は自動で載る。
  閉じたままのページ（racers・highlights など14本）は載せない。
- lastmod は各ファイルの最終コミット日時（git log -1 --format=%cI -- <path>）。
  履歴が取れないファイルがあれば推測で埋めずに止まる（Actions では fetch-depth: 0 が要る）。
- priority・changefreq は書かない（Google は使わない）。
- 開くページに noindex が残っていたら止まる（sitemap と noindex の食い違いを出さない）。

使い方: python3 scripts/buildSitemap.py
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "sitemap.xml")
BASE = "https://abeken1026395.github.io/pallas-mercato-7k9/"

VENUES = [
    "kiryu", "toda", "edogawa", "heiwajima", "tamagawa", "hamanako",
    "gamagori", "tokoname", "tsu", "mikuni", "biwako", "suminoe",
    "amagasaki", "naruto", "marugame", "kojima", "miyajima", "tokuyama",
    "shimonoseki", "wakamatsu", "ashiya", "fukuoka", "karatsu", "omura",
]

NOINDEX = re.compile(r'<meta name="robots" content="noindex', re.I)
KENSHO_LINK = re.compile(r'href="\./([a-z0-9]+)/"')


def kensho_pages():
    """/kensho/ ハブからリンクされている検証記事。公開のたびに手で足すと漏れる（kisetsu・jimoto の実例）。"""
    with open(os.path.join(ROOT, "docs", "kensho", "index.html"), encoding="utf-8") as f:
        slugs = list(dict.fromkeys(KENSHO_LINK.findall(f.read())))
    if not slugs:
        sys.exit("/kensho/ ハブから検証記事のリンクが1本も取れない")
    return ["kensho/%s/" % s for s in slugs]


# 開くページ（トップ／検証ハブと検証記事／用語辞典・24場・場の文化・実況アナ／万舟25本）
OPEN = (
    [""]
    + ["kensho/"] + kensho_pages()
    + ["glossary/", "stadium/", "fan/", "announcers/"]
    + ["payouts/"]
    + ["%s-payouts/" % v for v in VENUES]
)
FIXED = 1 + 1 + 4 + 1 + len(VENUES)   # 検証記事以外の本数（31本）


def lastmod(rel):
    r = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%cI", "--", rel],
                       capture_output=True, text=True, check=True)
    v = r.stdout.strip()
    if not v:
        sys.exit("lastmod が取れない: %s（履歴が浅い可能性。fetch-depth: 0 で取得する）" % rel)
    return v


def main():
    if len(set(OPEN)) != len(OPEN) or len(OPEN) - len(kensho_pages()) != FIXED:
        sys.exit("開くページの数が合わない: %d（検証記事以外は %d 本のはず）" % (len(OPEN), FIXED))
    rows = []
    for path in OPEN:
        rel = "docs/%sindex.html" % path
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            if NOINDEX.search(f.read()):
                sys.exit("開くページに noindex が残っている: %s" % rel)
        rows.append("  <url>\n    <loc>%s%s</loc>\n    <lastmod>%s</lastmod>\n  </url>"
                    % (BASE, path, lastmod(rel)))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(rows) + "\n</urlset>\n")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    print("sitemap: %d urls -> %s" % (len(rows), os.path.relpath(OUT, ROOT)))


if __name__ == "__main__":
    main()
