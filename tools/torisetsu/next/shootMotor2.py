import asyncio
from playwright.async_api import async_playwright
exec(open("shootNow.py").read().split("async def main")[0])
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,service_workers="block")
        await ctx.route("**/*",route)
        pg=await ctx.new_page(); errs=[]
        pg.on("pageerror",lambda e:errs.append(str(e)))
        await pg.goto(BASE+"/motor/",wait_until="networkidle"); await pg.wait_for_timeout(1800)
        info=await pg.evaluate("""(()=>{
          const n=[...document.querySelectorAll('*')].find(e=>e.childElementCount===0&&e.textContent.trim()==='奈須　啓太');
          let row=n; for(let i=0;i<6&&row;i++){ if(row.getAttribute&&row.getAttribute('role')==='button'||(row.onclick)) break; row=row.parentElement;}
          const a=n.closest('a'); return {tag:n.tagName, inA:!!a, href:a?a.getAttribute('href'):null,
             rowHTML:n.parentElement.parentElement.parentElement.outerHTML.slice(0,900)};})()""")
        print(info)
        await b.close()
asyncio.run(main())
