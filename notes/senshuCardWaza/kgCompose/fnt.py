import json,sys
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
S='/tmp/claude-0/-home-claude/029556a4-1edb-55a2-bb20-fe2eb339970b/scratchpad/'
F=TTFont(S+'kg/GN-KillGothic-U-KanaNB.ttf')
cmap=F.getBestCmap();gs=F.getGlyphSet();U=F['head'].unitsPerEm;ASC=F['hhea'].ascent
k=1000/U
class P(BasePen):
    def __init__(s,gs):super().__init__(gs);s.d=[]
    def T(s,p):return f'{round(p[0]*k)} {round((ASC-p[1])*k)}'
    def _moveTo(s,p):s.d.append('M'+s.T(p))
    def _lineTo(s,p):s.d.append('L'+s.T(p))
    def _qCurveToOne(s,a,b):s.d.append('Q'+s.T(a)+' '+s.T(b))
    def _curveToOne(s,a,b,c):s.d.append('L'+s.T(c))
    def _closePath(s):s.d.append('Z')
def glyph(ch):
    n=cmap.get(ord(ch))
    if n is None: return None
    p=P(gs);gs[n].draw(p);return [round(F['hmtx'][n][0]*k),''.join(p.d)]
