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
    white = (a > 225).all(axis=2).mean(axis=0)  # 列ごとの「白い」割合
    g = 0
    while g < w and white[g] > 0.3:            # 本体（画面）が始まるまでが余白帯（白地に丸と線だけ）
        g += 1
    while g < w and (a[:, g] < 120).all(axis=1).mean() < 0.45:  # 丸の線の切れ目を越えて、画面の始まりまで進める
        g += 1
    if 4 < g < w * 0.35:                       # 左の余白帯だけ塗り替える
        band = a[:, :g]
        m = (band > 225).all(axis=2)
        edge = a[:, min(g + 2, w - 1)][:, None, :].repeat(g, axis=1)  # 行ごとに、画面の左端と同じ色で塗る（地の色の帯を作らない）
        band[m] = edge[m]
        a[:, :g] = band
    out = Image.fromarray(a.astype(np.uint8))
    out.thumbnail((900, 4000), Image.LANCZOS)
    out.save("%s/%s.jpg" % (DST, f[:-4]), quality=74, optimize=True)
    print(f, "gutter", g)
