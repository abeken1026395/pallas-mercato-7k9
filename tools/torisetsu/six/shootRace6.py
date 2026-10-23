"""第6版の出走表から、g01 の図6枚を撮る。"""
import asyncio, sys
sys.path.insert(0, "/home/claude/six"); sys.path.insert(0, "/home/claude")
from shootLib import *

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await openPage(b, "racers.html")
        await grab(pg, "figVenueList", ".crumb", ".venue-card#3",
                   [".fortune-bar", ".date-head", ".venue-card#0 >> .venue-name", ".venue-card#1 >> .gbadge",
                    ".venue-card#2 >> node:12R｜", ".venue-card#3 >> .venue-day"], pad_bot=14)
        await pg.locator(".venue-card").first.click(); await pg.wait_for_timeout(1500)
        await grab(pg, "figRaceList", ".rgrid", "text^:観戦記#0",
                   [".rgrid >> .rbtn#0 >> .rno", ".rgrid >> .rbtn#0 >> .rdone",
                    ".rgrid >> .rbtn#8 >> .rbtn-down", ".legend-note#0", "text^:観戦記#0"], pad_bot=30)
        await pg.locator(".rgrid .rbtn").nth(6).click(); await pg.wait_for_timeout(1800)
        await grab(pg, "figRaceTop", ".race-head", ".race-head",
                   [".race-head >> .line1", ".race-head >> .cd", ".race-head >> node:トランスワード", ".race-head >> .watchbtn", ".race-head >> .offlink-card"])
        await grab(pg, "figRaceHead", ".chips", ".card-legend",
                   [".chips >> .chip#0", ".chips >> .chip#3", "details.mido >> summary",
                    ".sortbar", "details.ns#0 >> summary", "details.ns#1 >> summary", ".card-legend"])
        await grab(pg, "figBoatTop", ".boat#0", ".boat#0 >> .kmr",
                   [".boat#0 >> .boat-top", ".boat#0 >> .boat-sub", ".boat#0 >> .badges",
                    ".boat#0 >> .nums >> .h#0", ".boat#0 >> .nums >> .l#1", ".boat#0 >> .kinmotor", ".boat#0 >> .kmr"],
                   pad_top=4)
        await grab(pg, "figBoatBottom", ".boat#0 >> details.tj", ".boat#1 >> .boat-top",
                   [".boat#0 >> details.tj >> summary", ".boat#0 >> .cl10-hd", ".boat#0 >> text^:内訳#0",
                    ".boat#0 >> text^:1号艇で出たときの決着#0", ".boat#0 >> text^:今節成績#0", ".boat#1 >> .boat-top"])
        await b.close()
asyncio.run(main())
