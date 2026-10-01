import re, subprocess, io
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, ArrayObject
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

SRC = "raw.pdf"
DST = "/home/claude/データ攻めトリセツ.pdf"

txt = subprocess.run(["pdftotext", SRC, "-"], capture_output=True, text=True).stdout
anchor = {}
for i, t in enumerate(txt.split("\f")):
    for m in re.finditer(r"@@([A-Za-z0-9_]+)@@", t):
        anchor.setdefault(m.group(1), i)
print("anchors:", len(anchor))

r = PdfReader(SRC)
w = PdfWriter()
for p in r.pages:
    w.add_page(p)
n = len(w.pages)

fixed = 0
for p in w.pages:
    ann = p.get("/Annots")
    if ann is not None and hasattr(ann, "get_object"):
        ann = ann.get_object()
    for a in (ann or []):
        o = a.get_object()
        act = o.get("/A")
        if not act:
            continue
        m = re.search(r"#([A-Za-z0-9_]+)$", str(act.get("/URI", "")))
        if not m:
            continue
        tgt = anchor.get(m.group(1))
        if tgt is None:
            continue
        o[NameObject("/A")] = DictionaryObject({
            NameObject("/S"): NameObject("/GoTo"),
            NameObject("/D"): ArrayObject([w.pages[tgt].indirect_reference,
                                           NameObject("/Fit")]),
        })
        fixed += 1
print("internal links:", fixed)

OUTLINE = [
    ("もくじ", "top", []),
    ("第1部 はじめの3分", "p1", [
        ("1. ホーム画面に置く", "s11"),
        ("2. 今日の開催を見る", "s12"),
        ("3. 答え合わせの帯", "s13"),
        ("4. 場と選手を登録", "s14"),
        ("5. 1日の見る順番", "s15"),
    ]),
    ("第2部 困ったとき", "p2", [
        ("記号の見本", "s21"),
        ("おかしく見えるとき", "s22"),
        ("よくある質問", "s23"),
    ]),
    ("第3部 画面の辞書", "p3", [
        ("出走表", "g01"), ("見どころ", "g02"), ("モーター", "g03"),
        ("モーター整備", "g04"), ("24場のトリセツ", "g05"),
        ("選手図鑑", "g06"), ("レース結果", "g07"), ("万舟のツボ", "g08"),
        ("検証", "g09"), ("場の文化ほか", "g10"),
        ("用語辞典ほか", "g11"), ("やらないこと", "g12"),
    ]),
]
for title, key, children in OUTLINE:
    pg = anchor.get(key)
    if pg is None:
        print("  ! miss:", key)
        continue
    parent = w.add_outline_item(title, pg)
    for ct, ck in children:
        cp = anchor.get(ck)
        if cp is not None:
            w.add_outline_item(ct, cp, parent=parent)

for i, pg in enumerate(w.pages):
    if i == 0:
        continue
    W = float(pg.mediabox.width); H = float(pg.mediabox.height)
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=(W, H))
    c.setFillColor(HexColor("#8494a4")); c.setFont("Helvetica", 8)
    c.drawCentredString(W / 2, 12, "%d / %d" % (i + 1, n))
    c.save(); b.seek(0)
    pg.merge_page(PdfReader(b).pages[0])

w.add_metadata({"/Title": "データ攻めトリセツ 2026年9月30日版", "/Author": "あべけん"})
w.write(DST)
print("pages:", n)
