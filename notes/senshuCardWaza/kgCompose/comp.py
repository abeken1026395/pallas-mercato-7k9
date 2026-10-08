import sys,json
sys.path.insert(0,'/tmp/claude-0/-home-claude/029556a4-1edb-55a2-bb20-fe2eb339970b/scratchpad');sys.path.insert(0,'/home/claude/pallas-mercato-7k9/notes/senshuCardWaza')
import warnings;warnings.filterwarnings('ignore')
import logging;logging.disable(logging.CRITICAL)
from fnt import glyph
from sharpen import geom,to_path,sharpen
from shapely.geometry import box,LineString
from shapely.ops import unary_union
from shapely import affinity
_c={}
def G(ch):
    if ch not in _c:
        r=glyph(ch); assert r and r[1], ch
        _c[ch]=unary_union([geom(r[1])]).buffer(0)
    return _c[ch]
def bb(g): return g.bounds
def clip(g,b): return g.intersection(box(*b)).buffer(0)
def fit(g,dst,src=None):
    s=src or g.bounds
    sx=(dst[2]-dst[0])/(s[2]-s[0]); sy=(dst[3]-dst[1])/(s[3]-s[1])
    g=affinity.scale(g,sx,sy,origin=(s[0],s[1]))
    return affinity.translate(g,dst[0]-s[0],dst[1]-s[1])
def cov_x(g,x): return g.intersection(LineString([(x,-50),(x,1100)])).length
def cov_y(g,y): return g.intersection(LineString([(-50,y),(1100,y)])).length
def gapx(ch,lo,hi):
    g=G(ch); best=min(range(lo,hi,2),key=lambda x:(cov_x(g,x),abs(x-(lo+hi)/2)));
    # center of zero-run
    xs=[x for x in range(lo,hi,2) if cov_x(g,x)==cov_x(g,best)]
    run=[x for x in xs if abs(x-best)<60]; return (min(run)+max(run))//2
def gapy(ch,lo,hi):
    g=G(ch); best=min(range(lo,hi,2),key=lambda y:(cov_y(g,y),abs(y-(lo+hi)/2)))
    ys=[y for y in range(lo,hi,2) if cov_y(g,y)==cov_y(g,best)]
    run=[y for y in ys if abs(y-best)<60]; return (min(run)+max(run))//2
BIG=(-100,-100,1100,1100)
def L(ch,x): return clip(G(ch),(-100,-100,x,1100))
def R(ch,x): return clip(G(ch),(x,-100,1100,1100))
def T(ch,y): return clip(G(ch),(-100,-100,1100,y))
def B(ch,y): return clip(G(ch),(-100,y,1100,1100))
def U(*gs): return unary_union([g for g in gs if g is not None and not g.is_empty]).buffer(0)
def lr(donor,lo,hi,right,rsrc=None):
    """donor の左偏 + right を donor の右側の枠へ"""
    x=gapx(donor,lo,hi); return U(L(donor,x),fit(rsrc if rsrc is not None else G(right),bb(R(donor,x))))
def tb(donor,lo,hi,bottom,bsrc=None):
    y=gapy(donor,lo,hi); return U(T(donor,y),fit(bsrc if bsrc is not None else G(bottom),bb(B(donor,y))))
def raw_path(g): return to_path(g)
def big(g,frac=0.03):
    ps=[g] if g.geom_type=='Polygon' else [p for p in g.geoms if p.geom_type=='Polygon']
    tot=sum(p.area for p in ps); return U(*[p for p in ps if p.area>=tot*frac])
def mirror(g):
    b=g.bounds; return affinity.scale(g,-1,1,origin=((b[0]+b[2])/2,0))
def fitb(g,dst,t=30):
    s=g.bounds; sc=min((dst[2]-dst[0])/(s[2]-s[0]),(dst[3]-dst[1])/(s[3]-s[1]))
    k=t*max(0,1-sc)
    d=(dst[0]+k,dst[1]+k,dst[2]-k,dst[3]-k)
    return fit(g,d).buffer(k,join_style='mitre',mitre_limit=4.0)
