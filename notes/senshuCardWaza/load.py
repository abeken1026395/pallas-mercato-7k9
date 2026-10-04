import json,glob,os,pandas as pd,numpy as np
R='/home/claude/abeken1026395/pallas-mercato-7k9/'
rows=[];races=[]
for f in sorted(glob.glob(R+'results/*.json')):
    d=os.path.basename(f)[:8]
    j=json.load(open(f))
    for ri,r in enumerate(j['結果']):
        key=(d,r['場コード'],r['レース'])
        boats=r['艇']
        races.append(dict(date=d,jo=r['場コード'],race=r['レース'],kimarite=r.get('決まり手'),nb=len(boats),wind=r.get('風速'),wave=r.get('波高')))
        for b in boats:
            rows.append(dict(date=d,jo=r['場コード'],race=r['レース'],waku=b.get('枠'),toban=b['登番'],name=b['氏名'],course=b.get('コース'),st=b.get('ST'),chaku=b.get('着'),grade=b.get('級別'),kim=r.get('決まり手')))
df=pd.DataFrame(rows);rc=pd.DataFrame(races)
df.to_pickle('boats.pkl');rc.to_pickle('races.pkl')
print(len(df),len(rc))
print(df.chaku.value_counts().sort_index().to_dict())
print(df.course.value_counts(dropna=False).to_dict())
print(rc.kimarite.value_counts(dropna=False).to_dict())
print(rc.nb.value_counts().to_dict())
