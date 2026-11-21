"""キルゴUに無い2字（ツ・絞）を既存の字形から組む（2026-11-21）。使い方: python3 kgTsuShibo.py <kgOutline.json> <出力> [プレビューpng]"""
import json,re,sys
src=open(sys.argv[0].replace('kgTsuShibo.py','kg5.py')).read().split('D={}')[0].replace("K=json.load(open(sys.argv[1],encoding='utf-8'))","K=json.load(open(IN,encoding='utf-8'))")
IN=sys.argv[1];exec(src)
def colgap(g,x0,x1):
    best=None
    for x in range(x0,x1,5):
        a=g.intersection(box(x,-100,x+5,1100)).area
        if best is None or a<best[1]:best=(x,a)
    return best
D={}
t=G('ッ');D['ツ']=fit(t,(40,40,960,975),t.bounds)
k=G('結');sx=colgap(k,300,520)[0];left=clip(k,(-100,-100,sx+3,1100))
r=G('校');sx2=colgap(r,360,520)[0];right=clip(r,(sx2,-100,1100,1100))
D['絞']=un(left,right)
for c,g in D.items():
    Gs[c]=[1000 if c=='ツ' else 1040,to_path(g)];print(c,[round(v) for v in g.bounds],sx,sx2)
open(sys.argv[2],'w',encoding='utf-8').write(json.dumps(K,ensure_ascii=False,separators=(',',':')))
if len(sys.argv)>3:
    from PIL import Image,ImageDraw
    im=Image.new('L',(2400,600),255);d=ImageDraw.Draw(im)
    for i,c in enumerate('コツ絞結校'):
        g=geom(Gs[c][1]);ps=[g] if g.geom_type=='Polygon' else list(g.geoms)
        for p in ps:
            d.polygon([(x*0.45+i*470+20,y*0.45+60) for x,y in p.exterior.coords],fill=0)
            for h in p.interiors:d.polygon([(x*0.45+i*470+20,y*0.45+60) for x,y in h.coords],fill=255)
    im.save(sys.argv[3])
