#!/usr/bin/env python3
"""
docs/sitemap.xml を生成する（siteReachPlan20260911 V3）。

- 検索に開いている35本（2026-09-11 裁定の C案）の URL だけを列挙する。
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

# 開く35本（トップ／検証5本／用語辞典・24場・場の文化・実況アナ／万舟25本）
OPEN = (
    [""]
    + ["kensho/", "kensho/shobugake/", "kensho/taiju/", "kensho/fmochi/", "kensho/ninki/"]
    + ["glossary/", "stadium/", "fan/", "announcers/"]
    + ["payouts/"]
    + ["%s-payouts/" % v for v in VENUES]
)

NOINDEX = re.compile(r'<meta name="robots" content="noindex', re.I)


def lastmod(rel):
    r = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%cI", "--", rel],
                       capture_output=True, text=True, check=True)
    v = r.stdout.strip()
    if not v:
        sys.exit("lastmod が取れない: %s（履歴が浅い可能性。fetch-depth: 0 で取得する）" % rel)
    return v


def main():
    if len(OPEN) != 35 or len(set(OPEN)) != 35:
        sys.exit("開くページの数が35本ではない: %d" % len(OPEN))
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
