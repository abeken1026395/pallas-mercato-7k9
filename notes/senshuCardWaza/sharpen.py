"""キルゴUのアウトライン（kgOutline.json）を加工して、キルラキル寄りの C パターンを作る。
規約：アウトラインデータ化してからの改変は自由（readme.txt）。フォントファイル自体は触らない。
加工：①留め（マイター）で太らせて角を尖らせる ②横を詰めて縦長に ③右上がりに少し傾ける
"""
import json, re, sys
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import affinity
from shapely.validation import make_valid

def rings(d):
    toks = re.findall(r'[MLHVQZ]|-?\d+(?:\.\d+)?', d)
    i = 0; cur = []; out = []; x = y = 0; cmd = None
    while i < len(toks):
        t = toks[i]
        if t in 'MLHVQZ':
            cmd = t; i += 1
            if t == 'Z':
                if len(cur) >= 3: out.append(cur)
                cur = []
            continue
        if cmd == 'M':
            if len(cur) >= 3: out.append(cur)
            x, y = float(toks[i]), float(toks[i+1]); i += 2; cur = [(x, y)]; cmd = 'L'
        elif cmd == 'L':
            x, y = float(toks[i]), float(toks[i+1]); i += 2; cur.append((x, y))
        elif cmd == 'H':
            x = float(toks[i]); i += 1; cur.append((x, y))
        elif cmd == 'V':
            y = float(toks[i]); i += 1; cur.append((x, y))
        elif cmd == 'Q':
            cx, cy, ex, ey = map(float, toks[i:i+4]); i += 4
            for k in range(1, 7):
                t_ = k / 6
                px = (1-t_)**2*x + 2*(1-t_)*t_*cx + t_**2*ex
                py = (1-t_)**2*y + 2*(1-t_)*t_*cy + t_**2*ey
                cur.append((px, py))
            x, y = ex, ey
    if len(cur) >= 3: out.append(cur)
    return out

def geom(d):
    g = None
    for r in rings(d):
        p = make_valid(Polygon(r))
        g = p if g is None else g.symmetric_difference(p)
    return g

def to_path(g):
    parts = []
    polys = [g] if g.geom_type == 'Polygon' else [p for p in getattr(g, 'geoms', []) if p.geom_type == 'Polygon']
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            cs = list(ring.coords)[:-1]
            if len(cs) < 3: continue
            parts.append('M' + 'L'.join(f'{round(a)} {round(b)}' for a, b in cs) + 'Z')
    return ''.join(parts)

def sharpen(K, grow=16, sx=0.88, skew=-7):
    out = {'asc': K['asc'], 'g': {}}
    for ch, (adv, d) in K['g'].items():
        g = geom(d)
        if g is None or g.is_empty:
            out['g'][ch] = [round(adv*sx), d]; continue
        g = unary_union([g])
        if grow:
            g = g.buffer(grow, join_style='mitre', mitre_limit=4.0)
        g = affinity.scale(g, xfact=sx, yfact=1.0, origin=(0, 0))
        if skew:
            g = affinity.skew(g, xs=skew, origin=(0, 470))   # y が下向きなので負で右上がり
        out['g'][ch] = [round(adv*sx), to_path(g)]
    return out

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    grow, sx, skew = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
    K = json.load(open(src))
    C = sharpen(K, grow, sx, skew)
    json.dump(C, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(len(C['g']))
