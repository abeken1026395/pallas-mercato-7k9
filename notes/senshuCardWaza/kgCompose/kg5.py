"""キルゴUに無い5字（党・命・読・収・苦）を、kgOutline.json の既存の字形の部品から組む（2026-11-11）。
既存の字形は sharpen 済みなので、部品を切り出して並べるだけで太さの癖がそろう。使い方: python3 kg5.py <kgOutline.json> <出力>"""
import json,re,sys
from shapely.geometry import Polygon,box,MultiPolygon
from shapely.ops import unary_union
from shapely import affinity
K=json.load(open(sys.argv[1],encoding='utf-8'));Gs=K['g']
def geom(d):
    rings=[];cur=[];x=y=0
    for cmd,args in re.findall(r'([MLQZ])([^MLQZ]*)',d):
        n=[float(v) for v in args.split()]
        if cmd=='M':
            if len(cur)>2:rings.append(cur)
            x,y=n;cur=[(x,y)]
        elif cmd=='L':x,y=n;cur.append((x,y))
        elif cmd=='Q':
            cx,cy,ex,ey=n
            for i in range(1,9):
                t=i/8;cur.append(((1-t)**2*x+2*(1-t)*t*cx+t*t*ex,(1-t)**2*y+2*(1-t)*t*cy+t*t*ey))
            x,y=ex,ey
        elif cmd=='Z':
            if len(cur)>2:rings.append(cur)
            cur=[]
    if len(cur)>2:rings.append(cur)
    g=Polygon()
    for r in rings: g=g.symmetric_difference(Polygon(r).buffer(0))
    return g.buffer(0)
def G(ch):
    g=Gs[ch];assert g and g[1],ch;return geom(g[1])
def clip(g,b):return g.intersection(box(*b)).buffer(0)
def fit(g,dst,src=None):
    s=src or g.bounds
    g=affinity.scale(g,(dst[2]-dst[0])/(s[2]-s[0]),(dst[3]-dst[1])/(s[3]-s[1]),origin=(s[0],s[1]))
    return affinity.translate(g,dst[0]-s[0],dst[1]-s[1])
def to_path(g):
    ps=[g] if isinstance(g,Polygon) else list(g.geoms)
    out=[]
    for p in ps:
        if p.is_empty:continue
        p=p.simplify(1.0)
        for r in [p.exterior,*p.interiors]:
            c=list(r.coords)[:-1]
            out.append('M'+'L'.join(f'{round(a)} {round(b)}' for a,b in c)+'Z')
    return ''.join(out)
def un(*gs):return unary_union(gs).buffer(0)
D={}
# 苦＝若の艹（上）＋古（下に縮める）
t=clip(G('若'),(0,-100,1000,300));D['苦']=un(t,fit(G('古'),(G('古').bounds[0],310,G('古').bounds[2],G('古').bounds[3])))
# 党＝堂の⺌冖（上）＋兄（下）
t=clip(G('堂'),(0,-100,1000,470));b=G('兄');D['党']=un(t,fit(b,(b.bounds[0],480,b.bounds[2],b.bounds[3])))
# 読＝説の言偏＋続の売
D['読']=un(clip(G('説'),(0,-100,400,1100)),clip(G('続'),(400,-100,1100,1100)))
# 命＝令の人と一（上）＋口（左下）＋節の卩（右下）
t=clip(G('令'),(0,-100,1000,430));k=G('口')
pp=un(box(540,480,930,600),box(800,480,930,820),box(540,480,680,985))  # 卩は太さを口に合わせて矩形で組む
D['命']=un(t,fit(k,(70,500,480,880)),pp)
# 収＝左（レ＋縦棒）＋取の又
L=G('レ');m=clip(G('取'),(470,-100,1100,1100))
Lf=fit(L,(70,200,400,900),L.bounds)
bar=box(300,40,430,900)
D['収']=un(Lf,bar,fit(m,(450,m.bounds[1],950,m.bounds[3]),m.bounds))
for c,g in D.items():
    w=1000;Gs[c]=[w,to_path(g)]
    print(c,round(g.area),[round(v) for v in g.bounds])
open(sys.argv[2],'w',encoding='utf-8').write(json.dumps(K,ensure_ascii=False,separators=(',',':')))
