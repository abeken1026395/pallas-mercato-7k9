import os, numpy as np
from PIL import Image

SRC = "/home/claude/book"
DST = "/home/claude/next/img"
BG = (13, 39, 48)

for f in sorted(os.listdir(SRC)):
    if not (f.startswith("fig") and f.endswith(".png")):
        continue
    im = Image.open(SRC + "/" + f).convert("RGB")
    a = np.array(im).astype(np.int16)
    h, w, _ = a.shape
    dark = (a < 70).all(axis=2).mean(axis=0)  # 列ごとの「暗い」割合
    g = 0
    while g < w and dark[g] < 0.45:           # 本体（暗い画面）が始まるまでが余白帯
        g += 1
    if 4 < g < w * 0.35:                       # 左の余白帯だけ塗り替える
        band = a[:, :g]
        m = (band > 225).all(axis=2)
        band[m] = BG
        a[:, :g] = band
    out = Image.fromarray(a.astype(np.uint8))
    out.thumbnail((900, 4000), Image.LANCZOS)
    out.save("%s/%s.jpg" % (DST, f[:-4]), quality=74, optimize=True)
    print(f, "gutter", g)
