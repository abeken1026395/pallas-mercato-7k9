import asyncio, sys
sys.path.insert(0, "/home/claude/six"); sys.path.insert(0, "/home/claude")
import shootLib
from shootLib import *
from playwright.async_api import async_playwright
shootLib.BASE = BASE = "http://localhost:8112"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--lang=ja-JP"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=DSF, service_workers="block",
                                  reduced_motion="reduce", timezone_id="Asia/Tokyo", locale="ja-JP")
        await ctx.route("**/*", route)
        pg = await ctx.new_page()
        from datetime import datetime
        await pg.clock.set_fixed_time(datetime.fromisoformat("2026-11-07T13:33:00+09:00"))
        await pg.goto(BASE + "/", wait_until="networkidle"); await pg.wait_for_timeout(2000)
        await pg.click("#moreBtn"); await pg.wait_for_timeout(900)
        await pg.add_style_tag(content=".sheet{position:static!important;max-height:none!important;overflow:visible!important}.tb{position:static!important}.shbd{display:none!important}body{position:static!important}")
        await pg.wait_for_timeout(400)
        await grab(pg, "figTopTabs", ".sheet-in", ".tb",
                   [".sheet-in >> .sh2#0", ".sheet-in >> a[target=_blank]", ".sheet-in >> .sh2#3", ".sheet-in >> .hint", ".tb"],
                   pad_top=0, pad_bot=0)
        await b.close()
asyncio.run(main())
