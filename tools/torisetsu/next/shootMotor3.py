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
        await pg.evaluate("document.querySelector('[data-motor-row]').click()"); await pg.wait_for_timeout(1800)
        await pg.evaluate("document.querySelector('[data-motor-row]').scrollIntoView({block:'start'});window.scrollBy(0,-130)")
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=OUT+"/moRow.png")
        t=await pg.evaluate("document.body.innerText"); i=t.find("奈須")
        open(OUT+"/moRow.txt","w").write(t[i:i+1400])
        await pg.goto(BASE+"/motor/",wait_until="networkidle"); await pg.wait_for_timeout(1500)
        await pg.evaluate("""(()=>{const n=[...document.querySelectorAll('div,span,p')].reverse().find(e=>/^モーター新替/.test(e.textContent.trim()));
           n.scrollIntoView({block:'start'});window.scrollBy(0,-110);})()""")
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=OUT+"/moShingae.png")
        print("errors:",errs[:3])
        await b.close()
asyncio.run(main())
