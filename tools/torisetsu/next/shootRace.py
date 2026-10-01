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
        await pg.goto(BASE+"/racers/",wait_until="networkidle"); await pg.wait_for_timeout(1500)
        await pg.get_by_text("蒲郡",exact=True).first.click(); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=OUT+"/rcVenue.png",full_page=True)
        open(OUT+"/rcVenue.txt","w").write(await pg.evaluate("document.body.innerText"))
        # レースの一覧から 12R 以外の1つ（締切前）を開く
        els=pg.locator("text=/^\\d+R$/")
        n=await els.count(); print("R要素",n)
        await pg.get_by_text("8R",exact=True).first.click(); await pg.wait_for_timeout(2000)
        await pg.screenshot(path=OUT+"/rcRace.png",full_page=True)
        open(OUT+"/rcRace.txt","w").write(await pg.evaluate("document.body.innerText"))
        print("race 高さ",await pg.evaluate("document.documentElement.scrollHeight"))
        print("errors:",errs[:3])
        await b.close()
asyncio.run(main())
