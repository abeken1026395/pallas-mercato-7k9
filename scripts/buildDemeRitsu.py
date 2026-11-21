"""自分の記録の「猛者」の称号（2026-11-21 けん裁定）で使う、場ごとの2連単・3連単の出目の回数表を作る。
results/YYYYMMDD.json の直近365日（最終日を含む）から数える。出力 docs/note/demeRitsu.json
  n[場-1]：数えたレース数（1着から3着がそろったレース）
  t2[場-1][i]：2連単の組 C2[i] が出た回数。C2 は 1-2,1-3,…,6-5 の30通り（1着の艇番、2着の艇番の順）
  t3[場-1][i]：3連単の組 C3[i] が出た回数。C3 は 1-2-3,1-2-4,…,6-5-4 の120通り
使い方: python scripts/buildDemeRitsu.py [最終日 YYYYMMDD]（省略時は results/ の最新日）
半年に1回作り直す（期間はファイルの from・to に残る）"""
import json,os,sys,itertools,datetime
R='results'
days=sorted(f[:8] for f in os.listdir(R) if f.endswith('.json') and f[:8].isdigit())
to=sys.argv[1] if len(sys.argv)>1 else days[-1]
fr=(datetime.date(int(to[:4]),int(to[4:6]),int(to[6:]))-datetime.timedelta(days=364)).strftime('%Y%m%d')
C2=['%d-%d'%p for p in itertools.permutations(range(1,7),2)]
C3=['%d-%d-%d'%p for p in itertools.permutations(range(1,7),3)]
i2={c:i for i,c in enumerate(C2)};i3={c:i for i,c in enumerate(C3)}
n=[0]*24;t2=[[0]*30 for _ in range(24)];t3=[[0]*120 for _ in range(24)]
for d in days:
    if d<fr or d>to:continue
    for r in json.load(open(os.path.join(R,d+'.json'),encoding='utf-8')).get('結果',[]):
        try:j=int(r['場コード'])-1;a,b,c=r['1着'],r['2着'],r['3着']
        except Exception:continue
        if not(0<=j<24) or not all(x in range(1,7) for x in (a,b,c)) or len({a,b,c})<3:continue
        n[j]+=1;t2[j][i2['%d-%d'%(a,b)]]+=1;t3[j][i3['%d-%d-%d'%(a,b,c)]]+=1
out={'v':1,'from':fr,'to':to,'n':n,'t2':t2,'t3':t3}
os.makedirs('docs/note',exist_ok=True)
open('docs/note/demeRitsu.json','w',encoding='utf-8').write(json.dumps(out,separators=(',',':')))
print(fr,to,sum(n),'races')
