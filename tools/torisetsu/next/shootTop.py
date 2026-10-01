"""トップの図3枚（figTopNav・figTopKaisai・figTopKensho）を今の画面で撮り直す。"""
import asyncio, sys
from playwright.async_api import async_playwright

_src = open("/home/claude/next/shootFigs.py", encoding="utf-8").read().rsplit("asyncio.run(main())", 1)[0]
exec(_src)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=DSF, service_workers="block")
        await ctx.route("**/*", route)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(BASE + "/", wait_until="networkidle")
        await pg.wait_for_timeout(2000)
        for name, top, bottom, marks, kw in SPECS:
            await grab(pg, name, top, bottom, marks, **kw)
        print("errors:", errs[:3])
        await b.close()

SPECS = [
    ("figTopNav", ".hd", "#tdRest",
     [".promise", ".guide", ".quick", "#updateline", ".sec#0", "#tdCard >> .date", "#tdMark >> *#0", "#tdRest"],
     {"pad_top": -60}),
    ("figTopKaisai", "#tdPeaks >> li#0", ".tb >> .dayh",
     ["#tdPeaks >> li#0", "#exBtn", ".cta", ".homeHint", ".sec#1", "#dayBox"],
     {"pad_bot": 120}),
    ("figTopKensho", ".sec#1", "text^:上：見立て#0",
     ["#tbUpd", "#dayBox >> .dayh", "#dayBox >> .dayr#0", "#dayBox >> .dayr#1", "#dNote", ".tbt", ".row.are >> .rv"],
     {"pad_top": -20, "pad_bot": 30}),
]

if __name__ == "__main__":
    asyncio.run(main())
