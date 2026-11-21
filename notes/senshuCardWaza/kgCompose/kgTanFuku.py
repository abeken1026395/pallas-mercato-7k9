"""キルゴUに無い3字（単・複・送）を既存の字形から組む（2026-11-21）。使い方: python3 kgTanFuku.py <kgOutline.json> <出力> [プレビューpng]"""
import json,re,sys,os
IN=sys.argv[1]
src=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'kg5.py'),encoding='utf-8').read().split('D={}')[0].replace("K=json.load(open(sys.argv[1],encoding='utf-8'))","K=json.load(open(IN,encoding='utf-8'))")
exec(src)
def colgap(g,x0,x1):
    best=None
    for x in range(x0,x1,5):
        a=g.intersection(box(x,-100,x+5,1100)).area
        if best is None or a<best[1]:best=(x,a)
    return best[0]
def rowgap(g,y0,y1,x0=-100,x1=1100):
    best=None
    for y in range(y0,y1,5):
        a=g.intersection(box(x0,y,x1,y+5)).area
        if best is None or a<best[1]:best=(y,a)
    return best[0]
D={}
# 単＝戦の左（単）を横に広げる
g=G('戦');sx=colgap(g,520,700);t=clip(g,(-100,-100,sx,1100));D['単']=fit(t,(60,t.bounds[1],940,t.bounds[3]),t.bounds)
# 複＝裕の衤＋（年の上の𠂉・日・夏の夂）で复
g=G('裕');sx=colgap(g,330,500);L=clip(g,(-100,-100,sx,1100))
y=G('年');top=clip(y,(-100,-100,1100,rowgap(y,250,420)));top=fit(top,(470,15,980,300),top.bounds)
hi=G('日');hi=fit(hi,(560,300,900,600),hi.bounds)
n=G('夏');yb=rowgap(n,520,700);bt=clip(n,(-100,yb,1100,1100));bt=fit(bt,(440,610,1000,980),bt.bounds)
D['複']=un(L,top,hi,bt)
# 送＝通の辶＋咲の关
g=G('通');sx=colgap(g,250,420);yb=rowgap(g,760,900,sx,1100)
sh=un(clip(g,(-100,-100,sx,1100)),clip(g,(sx,yb,1100,1100)))
k=G('咲');kx=colgap(k,300,480);r=clip(k,(kx,-100,1100,1100));D['送']=un(sh,fit(r,(sx+40,20,970,yb-30),r.bounds))
for c,gg in D.items():Gs[c]=[1000,to_path(gg)];print(c,[round(v) for v in gg.bounds])
open(sys.argv[2],'w',encoding='utf-8').write(json.dumps(K,ensure_ascii=False,separators=(',',':')))
if len(sys.argv)>3:
    from PIL import Image,ImageDraw
    cs='単戦複裕送通咲'
    im=Image.new('L',(470*len(cs),560),255);d=ImageDraw.Draw(im)
    for i,c in enumerate(cs):
        gg=geom(Gs[c][1]);ps=[gg] if gg.geom_type=='Polygon' else list(gg.geoms)
        for p in ps:
            d.polygon([(x*0.45+i*470+10,y*0.45+40) for x,y in p.exterior.coords],fill=0)
            for h in p.interiors:d.polygon([(x*0.45+i*470+10,y*0.45+40) for x,y in h.coords],fill=255)
    im.save(sys.argv[3])
