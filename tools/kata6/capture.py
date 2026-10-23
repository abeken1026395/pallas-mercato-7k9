import asyncio,re,sys,json,os
from playwright.async_api import async_playwright
import os
HERE=os.path.dirname(os.path.abspath(__file__))+"/"
S=os.environ.get("CAPOUT", HERE+"cap/")
os.makedirs(S,exist_ok=True)
BASEURL=os.environ.get("CAPBASE","http://localhost:8130/")
K=open(HERE+"kata5.js",encoding="utf-8").read().replace('var KEEP = "','var KEEP = "⚡📍',1)  # 本番の kata.js と同じく、⚡（いちばん荒れそうなレース）と📍（場のフォロー）は残す
a="  var KP = new WeakMap(), recording = 0, _sp = CSSStyleDeclaration.prototype.setProperty;"
assert K.count(a)==1
b="    var m = null;\n    if (recording) {"
assert K.count(b)==1
KC=K.replace(a,a+" window.__KP = KP;").replace(b,"    if (this.__o === undefined) this.__o = this.cssText;\n"+b).encode()
AN=open(HERE+"analyze.js").read()
# 外の CDN の React・Babel は、手元の同じ版で代わりにする（無いと React で描くページ（24場・場の文化など）が描かれず、写し取れない）
V=os.environ.get("VENDOR","/home/claude/vendor/")
VEND={"react.production.min.js":V+"react-18.2.0/umd/react.production.min.js","react-dom.production.min.js":V+"react-dom-18.2.0/umd/react-dom.production.min.js","babel.min.js":V+"babel.min.js"}
TABS="""(()=>{const sel='[role=tab],.tab,.tabs > *,.chip,.chipbtn,.dsw-btn,.rbtn,button';const out=[];const seen=new Set();for(const e of document.querySelectorAll(sel)){if(!e.getClientRects().length)continue;if(e.closest('a[href]'))continue;const p=e.parentElement;if(!p)continue;const sib=[...p.children].filter(c=>c.tagName===e.tagName);if(sib.length<2||sib.length>14)continue;if(seen.has(p))continue;seen.add(p);sib.forEach((c,i)=>{if(c.getClientRects().length)out.push([[...document.querySelectorAll(sel)].indexOf(c)])})}return out.slice(0,24).map(x=>x[0])})()"""
async def one(b,u,click=None,cand=None):
    pg=await b.new_page(viewport={"width":390,"height":844},has_touch=True,is_mobile=True)
    async def ext(r,*x):
        f=r.request.url.split("?")[0].rsplit("/",1)[-1]
        if f in VEND: await r.fulfill(path=VEND[f],content_type="application/javascript")
        elif "fonts.g" in r.request.url and os.environ.get("CAPFONTS"): await r.continue_()
        else: await r.abort()
    await pg.route(re.compile(r"https://"),ext)
    await pg.add_init_script("window.__ko0=new WeakMap();new MutationObserver(ms=>ms.forEach(m=>{if(!__ko0.has(m.target))__ko0.set(m.target,m.oldValue||'')})).observe(document,{attributes:true,attributeOldValue:true,attributeFilter:['style'],subtree:true})")
    await pg.route(re.compile(r".*/(kata5|cap)\.js.*"),lambda r,*x: r.fulfill(body=KC,content_type="application/javascript"))
    await pg.goto(BASEURL+u); await pg.wait_for_timeout(5200)
    tabs=None
    if click is None: tabs=await pg.evaluate(TABS)
    else:
        if isinstance(click,str) and click.startswith("loc:"):   # 開いて読む部品（選手図鑑の選手など）を開いた状態
            try: await pg.locator(click[4:]).first.click()
            except Exception: pass
            await pg.wait_for_timeout(1800)
        else:
          try:
            await pg.evaluate("i=>{const sel='[role=tab],.tab,.tabs > *,.chip,.chipbtn,.dsw-btn,.rbtn,button';const e=[...document.querySelectorAll(sel)][i];e.scrollIntoView({block:'center'});e.click()}",click)
          except Exception as ex: pass
          await pg.wait_for_timeout(1500)
    await pg.evaluate("document.querySelectorAll('details:not([open])').forEach(d=>d.open=true)"); await pg.wait_for_timeout(1500)
    if cand is not None: await pg.evaluate("c=>{window.__CAND=c}",cand)
    r=await pg.evaluate(AN); await pg.close(); return r,tabs
NAMES=dict(x.split('=',1)[::-1] for x in os.environ.get('CAPNAMES','').split(',') if '=' in x)
async def main():
    pages=sys.argv[1:]
    async with async_playwright() as p:
        b=await p.chromium.launch()
        sem=asyncio.Semaphore(4)
        async def page(u):
          async with sem:
            await page1(u)
        async def page1(u):
            r0,tabs=await one(b,u)
            tabs=list(tabs or [])+["loc:"+x.split("|",1)[1] for x in os.environ.get("CAPEXTRA","").split(";") if x.startswith(u+"|")]
            runs=[r0]
            for i in (tabs or []):
                r,_=await one(b,u,i); runs.append(r)
            merged={}; bad=set()
            for r in runs:
                for s,o in r["rules"].items():
                    for k,v in o.items():
                        key=(s,k)
                        if key in merged and merged[key]!=v: bad.add(key)
                        merged[key]=v
            for key in bad: merged.pop(key,None)
            base=set((s,k) for s,o in r0["rules"].items() for k in o)
            cand={}
            for (s,k),v in merged.items():
                # 最初の状態（開いたときの画面）で作った規則はそのまま使う。ほかの状態でだけ作れた規則と、
                # class・id・属性を持たない形だけの規則（div:nth-of-type(4)>… のような）は、全部の状態で確かめる（開いた中身の別の部品に当たるため）
                if (s,k) not in base or not re.search(r"[.#\[]", s): cand.setdefault(s,{})[k]=[v,1]
            rej=set()
            if len(runs)>1:
                for i in [None]+list(tabs or []):
                    r,_=await one(b,u,i,cand)
                    rej|=set(map(tuple,r["rej"]))
            for key in rej: merged.pop(key,None)
            out={}
            for (s,k),v in merged.items(): out.setdefault(s,{})[k]=v
            nm=NAMES.get(u, u.replace("/","_").replace(".html",""))
            json.dump({"miss":runs[0].get("miss"),"rules":out,"runs":[(r["pairs"],r["cov"],r["els"]) for r in runs]},open(S+"cap_"+nm+".json","w"),ensure_ascii=False)
            print(u,"runs",len(runs),"pairs/cov",[(r["pairs"],r["cov"]) for r in runs][:4],"rules",len(out),"conflict",len(bad),"rejected",len(rej),flush=True)
        await asyncio.gather(*[page(u) for u in pages])
        await b.close()
asyncio.run(main())
