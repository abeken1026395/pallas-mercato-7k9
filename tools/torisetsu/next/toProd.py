"""next/index.html を本番（docs/torisetsu/）用に整えて書き出す。"""
import os, re, shutil

SRC = "/home/claude/next"
REPO = "/home/claude/pallas-mercato-7k9"
DST = REPO + "/docs/torisetsu"
URL = "https://abeken1026395.github.io/pallas-mercato-7k9/torisetsu/"
DESC = ("データ攻めの取扱説明書です。はじめの3分の使い方、記号の意味、"
        "おかしく見えるときの読み方、12の画面の見かたを、図と番号で引けます。")

os.makedirs(DST + "/img", exist_ok=True)
s = open(SRC + "/index.html", encoding="utf-8").read()

used = sorted(set(re.findall(r'src="img/(fig[A-Za-z]+\.jpg)"', s)))
for f in used:
    shutil.copy(SRC + "/img/" + f, DST + "/img/" + f)
shutil.copy(SRC + "/delaSub.woff2", DST + "/delaSub.woff2")
shutil.copy(SRC + "/fonts/fontsource-dela-gothic-one-5.3.0/package/LICENSE", DST + "/delaOFL.txt")

head = (
    '<!-- データ攻め by あべけん https://abeken1026395.github.io/pallas-mercato-7k9/ -->\n'
    '<!DOCTYPE html>\n<html lang="ja">\n<head>\n'
    '<meta charset="UTF-8">\n'
    '<meta name="robots" content="noindex, nofollow">\n'
    '<meta name="author" content="あべけん（データ攻め）">\n'
    '<link rel="canonical" href="' + URL + '">\n'
    '<meta name="description" content="' + DESC + '">\n'
    '<meta property="og:type" content="article">\n'
    '<meta property="og:title" content="データ攻め トリセツ">\n'
    '<meta property="og:description" content="' + DESC + '">\n'
    '<meta property="og:image" content="https://abeken1026395.github.io/pallas-mercato-7k9/icon512.png">\n'
    '<meta property="og:url" content="' + URL + '">\n'
    '<meta property="og:site_name" content="データ攻め">\n'
    '<meta name="twitter:card" content="summary">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    '<title>トリセツ | データ攻め</title>\n'
)
i = s.index('<meta name="description"')
j = s.index("\n", i) + 1
s = head + s[j:]

font = (
    '<link rel="preload" href="delaSub.woff2" as="font" type="font/woff2" crossorigin>\n'
    '<style>@font-face{font-family:\'Dela Gothic One\';font-weight:400;font-display:swap;'
    'src:url(delaSub.woff2) format(\'woff2\')}</style>'
)
assert '<link rel="stylesheet" href="fonts/local.css">' in s
s = s.replace('<link rel="stylesheet" href="fonts/local.css">', font)

# 版の表示は試作の道具。本番では出さない
s = re.sub(r"var VER='[a-z]+';document\.getElementById\('ver'\)\.textContent='版 '\+VER;\n?", "", s)
s = s.replace('<span id="ver"></span>', "")
assert "版 '" not in s and 'id="ver"' not in s

s = s.replace("</body>", '<script src="../assets/guard.js" defer></script>\n</body>')
open(DST + "/index.html", "w", encoding="utf-8").write(s)

print("html:", len(s.encode()), "バイト  画像:", len(used), "枚  書体:",
      os.path.getsize(DST + "/delaSub.woff2"), "バイト")
print("img参照:", len(re.findall(r'src="img/', s)), " guard:", s.count("assets/guard.js"),
      " noindex:", s.count("noindex"), " 外部フォント:", s.count("fonts.googleapis"))
