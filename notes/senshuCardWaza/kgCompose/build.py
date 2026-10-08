"""キルゴUに無い漢字27字を、同じ書体の部品から組み立てて kgOutline.json に足す（2026-10-08）。
書体ファイルは Drive の GN-KillGothic_U.zip（リポジトリには置かない）。fnt.py の S を展開先に書き換えて使う。
組み立て方：set1（偏＋旁）・set2（冠＋脚）・set3（込み入った字）。生の字形で組んでから sharpen(-14, 1.04, 0) を通す
（公開中の字形はすべてこの加工済み。sharpen 後の比較で一致を確認済み）。
"""
import json,sys
from set1 import D as A
from set2 import D as B
from set3 import D as C
from comp import to_path
from sharpen import sharpen
D={**A,**{k:v for k,v in B.items() if v is not None},**C}
S=sharpen({'asc':859,'g':{c:[1000,to_path(g)] for c,g in D.items()}},-14,1.04,0)['g']
p=sys.argv[1]; K=json.load(open(p,encoding='utf-8'))
for c,v in S.items(): K['g'][c]=v
open(p,'w',encoding='utf-8').write(json.dumps(K,ensure_ascii=False,separators=(',',':')))
print(len(S))
