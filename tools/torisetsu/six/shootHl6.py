"""第6版の見どころから、図2枚（figHlLegend・figHlCards）を撮る。"""
import asyncio, sys
sys.path.insert(0, "/home/claude/six"); sys.path.insert(0, "/home/claude")
from shootLib import *
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await openPage(b, "highlights.html")
        await pg.evaluate("document.querySelector('details.howto').open=true"); await pg.wait_for_timeout(600)
        await grab(pg, "figHlLegend", "details.howto", ".viewguide",
                   [".mtr-legend#0 >> .mtr-leg-item#0", ".mtr-legend#0 >> .mtr-leg-item#3", ".sym-legend >> .jimoto",
                    ".sym-legend >> .flag#0", ".sym-legend >> .up", ".sym-legend >> .bunrui#0", ".sym-legend >> .mtr-leg-item#5", ".viewguide"])
        await pg.evaluate("document.querySelector('details.howto').open=false"); await pg.wait_for_timeout(600)
        await grab(pg, "figHlCards", ".tabs", ".race#1",
                   [".tabs", ".race#0 >> .rname", ".race#0 >> .badge", ".race#0 >> .deadline", ".race#0 >> .rmitate"], pad_bot=10)
        await b.close()
asyncio.run(main())
