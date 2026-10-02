"""選手占いの図4枚（figUranai・figUranaiCheck・figUranaiMine・figUranaiRace）を撮る。shootFigs.py の grab を使う。"""
import asyncio, sys
sys.path.insert(0, "/home/claude/next")
import types
_src = open("/home/claude/next/shootFigs.py", encoding="utf-8").read()
S = types.ModuleType("S")
exec(_src.split("\nasync def main():")[0], S.__dict__)   # shootFigs は import すると撮影を始めるので、部品だけ取り込む
from playwright.async_api import async_playwright

BASE = S.BASE   # README の手順どおり python3 -m http.server 8112 -d docs で出したサイト

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=S.DSF, service_workers="block")
        await ctx.route("**/*", S.route)
        await ctx.add_init_script("try{localStorage.setItem('uranai_me',JSON.stringify({bd:'1990-04-01',bl:'O'}));localStorage.setItem('uranai_motion','off')}catch(e){}")  # 図は動きを止めて撮る
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(BASE + "/uranai/", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        await S.grab(pg, "figUranai", "h1", ".ent#1",
                     ["#today", ".tabs", "#inputPanel", "#seg", ".ent#0"], pad_top=14, pad_bot=14)
        await pg.wait_for_timeout(500)
        await S.grab(pg, "figUranaiCheck", "#checkTtl", "#howTtl",
                     ["table", ".verdict", "text^:レースごとの星の推し", "#chk7", "#howTtl"], pad_top=14, pad_bot=16)
        # あなたの勝負運（勝負運タブの先頭）
        await pg.click("#tab-shobu")
        await pg.wait_for_timeout(500)
        await S.grab(pg, "figUranaiMine", "#mycard", "#mycard",
                     ["#mycard .big", "#mycard .front .stack", "#mycard .say", "#flipbtn"], pad_top=14, pad_bot=14)
        # レースで占う（勝負運・締切に関係なく12Rが並ぶ最初の場の1R）
        await pg.click("#tab-shobu")
        await pg.click('#scope button[data-s="race"]')
        await pg.select_option("#pv", index=0)
        await pg.click('#rchips button[data-r="1"]')
        await pg.wait_for_timeout(500)
        await S.grab(pg, "figUranaiRace", "#scope", ".ent#1",
                     ["#scope", "#pv", "#rchips", ".starpick", ".ent#0 >> .chip.star"], pad_top=14, pad_bot=14)
        print("errs", errs)
        await b.close()

asyncio.run(main())
