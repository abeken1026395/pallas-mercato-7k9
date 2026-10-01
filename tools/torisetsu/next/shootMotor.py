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
        # 見方を開く
        await pg.get_by_text("このデータの見方").first.click(); await pg.wait_for_timeout(700)
        await pg.screenshot(path=OUT+"/moHelp.png",full_page=False)
        t=await pg.evaluate("document.body.innerText")
        i=t.find("このデータの見方"); open(OUT+"/moHelp.txt","w").write(t[max(0,i-20):i+3000])
        await pg.screenshot(path=OUT+"/moHelpFull.png",full_page=True)
        await pg.goto(BASE+"/motor/",wait_until="networkidle"); await pg.wait_for_timeout(1500)
        # 1行開く（桐生の1行目）
        await pg.evaluate("window.scrollTo(0,0)")
        rows=pg.locator("text=奈須　啓太")
        await rows.first.click(); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=OUT+"/moRow.png",full_page=False)
        t=await pg.evaluate("document.body.innerText")
        i=t.find("奈須"); open(OUT+"/moRow.txt","w").write(t[i:i+1500])
        print("URL after row click:",pg.url)
        # 丸亀カード
        await pg.goto(BASE+"/motor/",wait_until="networkidle"); await pg.wait_for_timeout(1500)
        el=pg.get_by_text("丸亀",exact=True).first
        await el.scroll_into_view_if_needed(); await pg.evaluate("window.scrollBy(0,-80)"); await pg.wait_for_timeout(500)
        await pg.screenshot(path=OUT+"/moMarugame.png",full_page=False)
        print("errors:",errs[:3])
        await b.close()
asyncio.run(main())
