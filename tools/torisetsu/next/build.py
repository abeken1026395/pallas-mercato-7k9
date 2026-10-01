import re, os, shutil

SRC = "/home/claude/book"
DST = "/home/claude/next"
os.makedirs(DST + "/img", exist_ok=True)
for f in []:
    pass

chunks = []
for f in ("p1.html", "p2.html", "p3a.html", "p3b.html"):
    t = open("%s/%s" % (SRC, f), encoding="utf-8").read().strip()
    t = re.sub(r'</body>\s*</html>\s*$', "", t).strip()
    assert t.startswith('<div class="partpage">') and t.endswith("</div>"), f
    chunks.append(t[len('<div class="partpage">'):-len("</div>")])
body = "\n".join(chunks)

body = re.sub(r'<span class="mk">@@[a-z0-9]+@@</span>\n?', "", body)
body = re.sub(r'<div class="back">.*?</div>\n?', "", body, flags=re.S)
body = re.sub(r'src="(fig[A-Za-z]+)\.png"',
              r'src="img/\1.jpg" loading="lazy" alt=""', body)
body = body.replace(' style="padding-left:0"', "")
for k in (1,2,3):
    body = body.replace('<div class="no">PART %d</div>' % k, '<div class="no">第%d部</div>' % k)
    body = body.replace('<div class="partttl bg%d" id="p%d">' % (k,k), '<div class="partttl bg%d" id="p%d" data-n="%d">' % (k,k,k))
# 「── 」は紙の作法。画面では太字と改行で分ける
body = re.sub(r'(<li>(?:<b>.*?</b>)) ── ', r'\1', body)
body = re.sub(r'(<li>)(<b>.*?</b>)──\s*', r'\1\2', body)

st = [0]
def _st(m):
    st[0] += 1
    return '<span class="n k%d">' % st[0]
body = re.sub(r'<span class="n">', _st, body)

pg = [len(re.findall(r'<h3 class="pg"', body))]

# 見出しごとに section で囲む（sticky が積み重ならないように）
body = re.sub(r'(<h3 class="(?:step|pg))', r'</section>\n<section class="sec">\n\1', body)
body = re.sub(r'(<div class="partttl)', r'</section>\n<section class="sec">\n\1', body)
body = body.lstrip()
if body.startswith("</section>"):
    body = body[len("</section>"):]
body = body + "\n</section>"

# もくじ
toc, i3, cur = [], 0, None
for m in re.finditer(r'<h3 class="(step|pg)[^"]*" id="([a-z0-9]+)">(.*?)</h3>', body, flags=re.S):
    hid, inner = m.group(2), m.group(3)
    clean = re.sub(r'<span class="(?:n k\d|tag[^"]*)">.*?</span>', "", inner, flags=re.S)
    ttl = re.sub(r'<[^>]+>', "", clean).strip()
    if hid.startswith("s1"):
        grp, mark, cls = "第1部 はじめの3分", hid[2], "k" + hid[2]
    elif hid.startswith("s2"):
        grp, mark, cls = "第2部 困ったとき", "", "dot"
    else:
        i3 += 1
        grp, mark, cls = "第3部 画面の辞書", "", "bar"
    if grp != cur:
        toc.append('<p class="gp">%s</p>' % grp)
        cur = grp
    ico = '<i class="%s">%s</i>' % (cls, mark)
    toc.append('<a href="#%s">%s%s</a>' % (hid, ico, ttl))

shell = open(DST + "/shell.html", encoding="utf-8").read()
cue = open(DST + "/cue.json", encoding="utf-8").read()
out = (shell.replace("__BODY__", body).replace("__TOC__", "\n".join(toc))
            .replace("__CUE__", "window.CUE=" + cue + ";")
            .replace("__FONTS__", '<link rel="stylesheet" href="fonts/local.css">'))
open(DST + "/index.html", "w", encoding="utf-8").write(out)

o = out.count("<div"), out.count("</div>"), out.count("<section"), out.count("</section>")
print("bytes:", len(out.encode()), "toc:", len(toc), "steps:", st[0], "pages:", pg[0])
print("div open/close:", o[0], o[1], " section open/close:", o[2], o[3])
