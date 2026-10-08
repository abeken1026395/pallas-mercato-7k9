from PIL import Image,ImageDraw,ImageFont
from comp import *
REF=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc',150,index=0)
def draw(d,g,ox,oy,s=0.18):
    polys=[g] if g.geom_type=='Polygon' else [p for p in getattr(g,'geoms',[]) if p.geom_type=='Polygon']
    for p in polys:
        d.polygon([(ox+x*s,oy+y*s) for x,y in p.exterior.coords],fill=0)
        for r in p.interiors: d.polygon([(ox+x*s,oy+y*s) for x,y in r.coords],fill=255)
def sheet(items,out,cols=6):
    W=400;H=200;rows=(len(items)+cols-1)//cols
    im=Image.new('L',(W*cols,H*rows),255);d=ImageDraw.Draw(im)
    for i,(ch,g) in enumerate(items):
        ox=(i%cols)*W;oy=(i//cols)*H
        d.text((ox+5,oy+10),ch,font=REF,fill=0)
        draw(d,g,ox+200,oy+10)
        d.rectangle([ox+200,oy+10,ox+380,oy+190],outline=180)
    im.save(out)
def shp(g):
    from sharpen import sharpen as sh
    p=to_path(g); r=sh({'asc':859,'g':{'x':[1000,p]}},-14,1.04,0)['g']['x'][1]
    return geom(r)
def sheet2(items,out,cols=6,s=0.3):
    W=int(1100*s)+10;rows=(len(items)+cols-1)//cols
    im=Image.new('L',(W*cols,W*rows),255);d=ImageDraw.Draw(im)
    for i,(ch,g) in enumerate(items):
        ox=(i%cols)*W;oy=(i//cols)*W
        draw(d,shp(g),ox+5,oy+5,s)
    im.save(out)
