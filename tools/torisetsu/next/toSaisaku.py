"""トリセツの作り直し（2026-11-07）：next/index.html から、本番の形と実験場の形を作る。

  python3 toSaisaku.py next   … docs/next/torisetsu.html と docs/next/torisetsuImg/（実験場）
  python3 toSaisaku.py prod   … docs/torisetsu/（本番。けんの「本番へ」のあとだけ）

本番の形は toProd.py と同じ頭に、いまの本番から写した「共通の型 第6版」の読み込み（kata6:head / kata6:body）を足したもの。
型の読み込みは tools/kata6/build.py が本番に入れたもので、トリセツの正本（book・shell）には無いため、ここで本番から写す。
実験場は、それを docs/next/ に置ける形にしたもの（画像と書体は torisetsuImg/ に置く）。
"""
import os, re, shutil, sys

SRC = "/home/claude/next"
REPO = "/home/claude/pallas-mercato-7k9"
PROD = REPO + "/docs/torisetsu/index.html"
CF_TAG = ('<!-- Cloudflare Web Analytics --><script type=\'module\' src=\'https://static.cloudflareinsights.com/beacon.min.js\' '
          'data-cf-beacon=\'{"token": "173925d64f4a495bac679b00505ea517"}\'></script><!-- End Cloudflare Web Analytics -->'
          '<script src=/assets/raihou.js defer></script>')
URL = "https://abeken1026395.github.io/pallas-mercato-7k9/torisetsu/"
DESC = ("データ攻めの取扱説明書です。はじめの3分の使い方、記号の意味、"
        "おかしく見えるときの読み方、12の画面の見かたを、図と番号で引けます。")


def block(s, name):
    i = s.index("<!-- kata6:%s -->" % name)
    j = s.index("<!-- /kata6:%s -->" % name) + len("<!-- /kata6:%s -->" % name)
    return s[i:j]


def prod_html():
    cur = open(PROD, encoding="utf-8").read()
    kh, kb = block(cur, "head"), block(cur, "body")
    s = open(SRC + "/index.html", encoding="utf-8").read()
    head = (
        '<!-- データ攻め by 阿部 https://abeken1026395.github.io/pallas-mercato-7k9/ -->\n'
        '<!DOCTYPE html>\n<html lang="ja">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        '<meta name="author" content="阿部（データ攻め）">\n'
        '<link rel="canonical" href="' + URL + '">\n'
        '<meta name="description" content="' + DESC + '">\n'
        '<meta property="og:type" content="article">\n'
        '<meta property="og:title" content="データ攻め トリセツ">\n'
        '<meta property="og:description" content="' + DESC + '">\n'
        '<meta property="og:image" content="https://abeken1026395.github.io/pallas-mercato-7k9/ogp.png">\n'
        '<meta property="og:url" content="' + URL + '">\n'
        '<meta property="og:site_name" content="データ攻め">\n'
        '<meta name="twitter:card" content="summary">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>トリセツ | データ攻め</title>\n'
    )
    i = s.index('<meta name="description"')
    j = s.index("\n", i) + 1
    s = head + s[j:]
    font = ('<link rel="preload" href="delaSub.woff2" as="font" type="font/woff2" crossorigin>\n'
            '<style>@font-face{font-family:\'Dela Gothic One\';font-weight:400;font-display:swap;'
            'src:url(delaSub.woff2) format(\'woff2\')}</style>')
    assert s.count('<link rel="stylesheet" href="fonts/local.css">') == 1
    s = s.replace('<link rel="stylesheet" href="fonts/local.css">', font)
    s = re.sub(r"var VER='[a-z]+';document\.getElementById\('ver'\)\.textContent='版 '\+VER;\n?", "", s)
    s = s.replace('<span id="ver"></span>', "")
    assert "版 '" not in s and 'id="ver"' not in s
    assert s.count("</head>") == 1 and s.count("</body>") == 1
    s = s.replace("</head>", kh + "\n</head>")
    s = s.replace("</body>", '<script src="../assets/guard.js" defer></script>\n' + CF_TAG + "\n" + kb + "\n</body>")
    return s


def used_imgs(s):
    return sorted(set(re.findall(r'src="img/(fig[A-Za-z]+\.jpg)"', s)))


def to_prod():
    s = prod_html()
    dst = REPO + "/docs/torisetsu"
    used = used_imgs(s)
    for f in used:
        shutil.copy(SRC + "/img/" + f, dst + "/img/" + f)
    for f in os.listdir(dst + "/img"):
        if f not in used:
            os.remove(dst + "/img/" + f)
    shutil.copy(SRC + "/delaSub.woff2", dst + "/delaSub.woff2")
    open(dst + "/index.html", "w", encoding="utf-8").write(s)
    print("prod html:", len(s.encode()), "バイト  画像:", len(used))


# 実験場では共通の枠が「トリセツ」と見分けられない（パスが next/ のため）。本番と同じ見え方にするため、下のタブだけ隠す
NEXT_CSS = ('<style>/* 実験場だけ：本番のトリセツと同じく、共通の枠の下のタブを出さない */'
            '.dzf-tb,.dzf-sh{display:none!important}body{padding-bottom:0!important}</style>')


def to_next():
    s = prod_html()
    used = used_imgs(s)
    s = s.replace('<link rel="canonical" href="' + URL + '">',
                  '<link rel="canonical" href="https://abeken1026395.github.io/pallas-mercato-7k9/next/torisetsu.html">')
    s = s.replace("<title>トリセツ | データ攻め</title>", "<title>トリセツ（実験場）| データ攻め</title>")
    s = s.replace('src="img/', 'src="torisetsuImg/')
    s = s.replace('href="delaSub.woff2"', 'href="torisetsuImg/delaSub.woff2"').replace("url(delaSub.woff2)", "url(torisetsuImg/delaSub.woff2)")
    s = s.replace("<!-- /kata6:head -->", "<!-- /kata6:head -->\n" + NEXT_CSS)
    di = REPO + "/docs/next/torisetsuImg"
    os.makedirs(di, exist_ok=True)
    for f in used:
        shutil.copy(SRC + "/img/" + f, di + "/" + f)
    for f in os.listdir(di):
        if f not in used and f != "delaSub.woff2":
            os.remove(di + "/" + f)
    shutil.copy(SRC + "/delaSub.woff2", di + "/delaSub.woff2")
    open(REPO + "/docs/next/torisetsu.html", "w", encoding="utf-8").write(s)
    print("next html:", len(s.encode()), "バイト  画像:", len(used),
          " img参照:", len(re.findall(r'src="torisetsuImg/', s)), " noindex:", s.count("noindex"),
          " 外部フォント:", s.count("fonts.googleapis"))


if __name__ == "__main__":
    {"next": to_next, "prod": to_prod}[sys.argv[1]]()
