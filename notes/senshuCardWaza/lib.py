import pandas as pd,numpy as np,json,glob,os
from scipy.special import gammaln
from scipy.optimize import minimize
R='/home/claude/abeken1026395/pallas-mercato-7k9/'
Y1=('20251003','20261002'); ALL=('20250715','20261002')
H1=('20251003','20260403'); H2=('20260404','20261002')
def load():
    df=pd.read_pickle('/tmp/claude-0/-home-claude/94cc7118-f7b4-5f44-94a8-f2c262b6ac1a/scratchpad/waza/boats.pkl')
    df=df[df.course.notna()].copy()   # 欠場(16)と進入なし(15の12件)を除く = 出走した艇のみ
    df['course']=df.course.astype(int)
    df['rid']=df.date+'_'+df.jo+'_'+df.race
    return df
def betabin_fit(k,n):
    k=np.asarray(k,float);n=np.asarray(n,float)
    m=n>0;k=k[m];n=n[m]
    def nll(p):
        a,b=np.exp(p)
        return -np.sum(gammaln(n+1)-gammaln(k+1)-gammaln(n-k+1)+gammaln(k+a)+gammaln(n-k+b)-gammaln(n+a+b)-gammaln(a)-gammaln(b)+gammaln(a+b))
    mu=max(k.sum()/n.sum(),1e-4)
    best=None
    for s in (3,20,80):
        r=minimize(nll,np.log([mu*s,(1-mu)*s]),method='Nelder-Mead',options=dict(xatol=1e-6,fatol=1e-6,maxiter=2000))
        if best is None or r.fun<best.fun:best=r
    return tuple(np.exp(best.x))
def eb(k,n,prior=None):
    """k,n Series indexed by player -> DataFrame with post mean, pct (smaller=better, 1..100)"""
    k=k[n>0];n=n[n>0]
    a,b=prior if prior else betabin_fit(k.values,n.values)
    pm=(k+a)/(n+a+b)
    rank=pm.rank(ascending=False,method='min')
    out=pd.DataFrame({'k':k,'n':n,'raw':k/n,'pm':pm,'rank':rank,'pct':rank/len(pm)*100})
    out.attrs['prior']=(a,b)
    return out
def inper(df,per): return df[(df.date>=per[0])&(df.date<=per[1])]
def tally(ev,per):
    """ev: DataFrame with toban,date,opp(1 if denominator),hit(0/1). returns k,n series by toban"""
    e=inper(ev,per)
    g=e.groupby('toban')
    return g.hit.sum(),g.opp.sum()
def retention(ev,mins=range(3,16),top=20,per1=H1,per2=H2,prior_from_each=True,minn2=0):
    k1,n1=tally(ev,per1);k2,n2=tally(ev,per2)
    e1=eb(k1,n1);e2=eb(k2,n2)
    rows=[]
    for m in mins:
        S=e1[(e1.pct<=top)&(e1.k>=m)].index
        if len(S)==0: rows.append((m,0,np.nan));continue
        S2=[t for t in S if t in e2.index]
        ret=np.mean([e2.loc[t,'pct']<=top for t in S2]) if S2 else np.nan
        rows.append((m,len(S),ret,len(S2)))
    return pd.DataFrame(rows,columns=['min','nS','ret','nS2'][:len(rows[0])])
