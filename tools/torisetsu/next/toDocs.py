"""next/index.html を実験場（docs/next/torisetsu.html）用に整えて書き出す。"""
import os, re, shutil

SRC = "/home/claude/next"
REPO = "/home/claude/pallas-mercato-7k9"
DSTH = REPO + "/docs/next/torisetsu.html"
DSTI = REPO + "/docs/next/torisetsuImg"

os.makedirs(DSTI, exist_ok=True)
n = 0
for f in sorted(os.listdir(SRC + "/img")):
    if f.endswith(".jpg"):
        shutil.copy(SRC + "/img/" + f, DSTI + "/" + f)
        n += 1

s = open(SRC + "/index.html", encoding="utf-8").read()

head = (
    '<!-- データ攻め by あべけん https://abeken1026395.github.io/pallas-mercato-7k9/ -->\n'
    '<!DOCTYPE html>\n<html lang="ja">\n<head>\n'
    '<meta name="robots" content="noindex, nofollow">\n'
    '<meta charset="utf-8">\n'
    '<meta name="author" content="あべけん（データ攻め）">\n'
    '<link rel="canonical" href="https://abeken1026395.github.io/pallas-mercato-7k9/next/torisetsu.html">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    '<title>トリセツ（実験場）| データ攻め</title>\n'
)
old_head = s[:s.index("<meta name=\"description\"")]
assert "<!DOCTYPE html>" in old_head
s = head + s[s.index('<meta name="description"'):]

s = s.replace('src="img/', 'src="torisetsuImg/')
s = s.replace('<link rel="stylesheet" href="fonts/local.css">',
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&display=swap">')
s = s.replace("</body>", '<script src="../assets/guard.js" defer></script>\n</body>')

open(DSTH, "w", encoding="utf-8").write(s)
print("html:", len(s.encode()), "バイト  画像:", n, "枚")
print("img参照:", len(re.findall(r'src="torisetsuImg/', s)),
      " guard:", s.count("assets/guard.js"),
      " noindex:", s.count("noindex"))
