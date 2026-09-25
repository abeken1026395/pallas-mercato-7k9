# -*- coding: utf-8 -*-
# figShape.py … 本文の図「24場の山と谷の差」を venueShape.csv と summary.json から描く（インラインSVG）
# 出力：引数のパス（無ければ標準出力）。1行のSVG。
import io
import os
import sys
import csv
import json

HERE = os.path.dirname(os.path.abspath(__file__))
X0, X1 = 62.0, 330.0           # 横軸 −4 から +6 ポイント
LO, HI = -4.0, 6.0
Y0, DY = 40.0, 12.2
GRID = "#4a627f"; DIM = "#8a94a3"; FG = "#e0e6ed"; HL = "#ffd166"


def x(v):
    return X0 + (v - LO) / (HI - LO) * (X1 - X0)


def main():
    rows = list(csv.DictReader(io.open(os.path.join(HERE, "venueShape.csv"), encoding="utf-8")))
    summ = json.load(io.open(os.path.join(HERE, "summary.json"), encoding="utf-8"))
    rows.sort(key=lambda r: -float(r["S"]))
    H = Y0 + DY * (len(rows) - 1) + 12
    o = []
    for t in range(-4, 7, 2):
        o.append('<line x1="%.1f" y1="30" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%s"/>'
                 % (x(t), x(t), H - 4, GRID if t else DIM, "0.6" if t else "1"))
        o.append('<text x="%.1f" y="26" font-size="10" fill="%s" text-anchor="middle">%s</text>'
                 % (x(t), DIM, ("+%d" % t) if t > 0 else ("−%d" % -t if t < 0 else "0")))
    o.append('<text x="%.1f" y="11" font-size="10" fill="%s" text-anchor="end">← 2Rから4Rが堅い</text>' % (x(0) - 4, DIM))
    o.append('<text x="%.1f" y="11" font-size="10" fill="%s">10Rから12Rが堅い →</text>' % (x(0) + 4, DIM))
    xn = x(summ["Snational"])
    o.append('<line x1="%.1f" y1="30" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1" stroke-dasharray="3 3"/>'
             % (xn, xn, H - 4, FG))
    for i, r in enumerate(rows):
        y = Y0 + DY * i
        s = float(r["S"]); m = float(r["minDiff"])
        rev = s < 0 and abs(s) >= m
        out = abs(s) >= m
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="7" fill="%s" opacity="0.45"/>'
                 % (x(-m), y - 3.5, x(m) - x(-m), GRID))
        o.append('<text x="56" y="%.1f" font-size="10" fill="%s" text-anchor="end">%s</text>'
                 % (y + 3.5, FG if rev else DIM, r["venue"]))
        o.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s"/>'
                 % (x(s), y, "4" if rev else "3", HL if rev else (FG if out else DIM)))
        o.append('<text x="358" y="%.1f" font-size="10" fill="%s" text-anchor="end">%s</text>'
                 % (y + 3.5, DIM, ("%.2f" % s).replace("-", "−")))
    svg = ('<svg viewBox="0 0 360 %.0f" width="100%%" xmlns="http://www.w3.org/2000/svg">%s</svg>'
           % (H, "".join(o)))
    if len(sys.argv) > 1:
        io.open(sys.argv[1], "w", encoding="utf-8", newline="\n").write(svg)
    else:
        sys.stdout.write(svg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
