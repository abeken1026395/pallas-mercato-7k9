import asyncio
from playwright.async_api import async_playwright
exec(open("shootNow.py").read().split("async def main")[0])
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=1,service_workers="block")
        await ctx.route("**/*",route)
        pg=await ctx.new_page()
        await pg.goto(BASE+"/racers/",wait_until="networkidle"); await pg.wait_for_timeout(1200)
        await pg.get_by_text("蒲郡",exact=True).first.click(); await pg.wait_for_timeout(1000)
        await pg.get_by_text("8R",exact=True).first.click(); await pg.wait_for_timeout(1500)
        r=await pg.evaluate("""(()=>{
          const out=[];
          const walk=(el,d)=>{ if(d>9) return;
            for(const c of el.children){
              const cls=(c.className&&c.className.baseVal===undefined)?c.className:'';
              const r=c.getBoundingClientRect();
              if(r.height>0 && cls) out.push(' '.repeat(d)+c.tagName+'.'+cls.split(' ').join('.')+' y='+Math.round(r.top+scrollY)+' h='+Math.round(r.height)+' | '+(c.innerText||'').slice(0,30).replace(/\\n/g,' '));
              walk(c,d+1);} };
          walk(document.body,0); return out.slice(0,140).join('\\n');})()""")
        print(r)
        await b.close()
asyncio.run(main())
