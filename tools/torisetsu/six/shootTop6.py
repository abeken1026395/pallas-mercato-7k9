"""第6版のトップ（docs/next/topI.html）から、図3枚を撮る。"""
import asyncio, sys
sys.path.insert(0, "/home/claude/six"); sys.path.insert(0, "/home/claude")
from shootLib import *
SPECS = [
    ("figTopNav", ".byline", "#tdRest",
     [".promise", ".guide", ".quick", "#updateline", ".sec#0", "#tdCard >> .date", "#tdMark >> *#0", "#tdRest"],
     {"pad_top": 4}),
    ("figTopKaisai", "#tdPeaks >> li#0", ".sec#2",
     ["#tdPeaks >> li#0", "#exBtn", ".cta", ".homeHint", ".sec#1", ".sec#2"],
     {"pad_bot": 16}),
    ("figTopKensho", ".sec#2", "text^:上：見立て#0",
     ["#tbUpd", "#dayBox >> .dayh", "#dayBox >> .dayr#0", "#dayBox >> .dayr#1", "#dNote", ".tbt", ".row.are >> .rv"],
     {"pad_top": -20, "pad_bot": 30}),
]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await openPage(b, "topI.html", at="2026-10-24T09:10:00+09:00")
        for name, top, bottom, marks, kw in SPECS:
            try: await grab(pg, name, top, bottom, marks, **kw)
            except SystemExit as e: print("NG", e)
        await b.close()
asyncio.run(main())
