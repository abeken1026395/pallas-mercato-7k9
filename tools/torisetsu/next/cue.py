import os, json, numpy as np
from PIL import Image

SRC = "/home/claude/book"
OUT = "/home/claude/next/cue.json"
ORANGE = np.array([255, 122, 0])

cues = {}
for f in sorted(os.listdir(SRC)):
    if not (f.startswith("fig") and f.endswith(".png")):
        continue
    a = np.array(Image.open(SRC + "/" + f).convert("RGB")).astype(np.int16)
    h, w, _ = a.shape
    band = a[:, :110]                                   # 左の余白帯＝丸がある所
    hit = (np.abs(band - ORANGE).sum(axis=2) < 30)
    rows = np.where(hit.sum(axis=1) > 20)[0]            # 丸の走査線
    runs, cur = [], [int(rows[0])]
    for y in rows[1:]:
        if y - cur[-1] > 2:
            runs.append((cur[0], cur[-1])); cur = []
        cur.append(int(y))
    runs.append((cur[0], cur[-1]))
    ys = []
    for s0, e0 in runs:                                  # くっついた丸を分ける
        n = max(1, round((e0 - s0 + 1) / 69))
        step = (e0 - s0 + 1) / n
        for k in range(n):
            ys.append(s0 + step * (k + 0.5))
    cues[f[:-4]] = {
        "ar": round(w / h, 4),
        "cx": round(52 / w, 5),
        "r":  round(46 / w, 5),
        "ys": [round(y / h, 5) for y in ys],
    }
    print(f[:-4], len(ys))

json.dump(cues, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print("→", OUT)
