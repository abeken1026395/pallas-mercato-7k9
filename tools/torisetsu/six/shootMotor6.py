"""第6版のモーター（motorE）から、図3枚を撮る。"""
import asyncio, sys
sys.path.insert(0, "/home/claude/six"); sys.path.insert(0, "/home/claude")
from shootLib import *
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await openPage(b, "motor.html")
        await grab(pg, "figMotor", "h1", "text^:▼ 残り#0",
                   ["h1", "text^:各場のモーターを2連率#0", "node:最終更新", "text^:▼ このデータの見方#0", "select",
                    "node:10/21時点", "node:前節いちばん出ていた機", "node:選手（級別・機力）",
                    "[data-motor-row]#0", "text^:▼ 残り#0"], pad_top=6)
        await pg.evaluate("document.querySelector('[data-motor-row]').click()"); await pg.wait_for_timeout(1500)
        X = "[data-motor-row] + div >> "
        await grab(pg, "figMotorRow", "[data-motor-row]#0", X + "node:出典",
                   ["[data-motor-row]#0", X + "node:新替からの成績", X + "node:公式", X + "node:節ごとの着順",
                    X + "node:整備履歴", X + "node:部品交換", X + "node:もすべて見る", X + "node:出典"], pad_top=4)
        pg = await openPage(b, "motor.html")
        await grab(pg, "figMotorShingae", "node:10/20時点", "[data-motor-row]#23",
                   ["node:10/20時点", "node:モーター新替", "[data-motor-row]#21", "[data-motor-row]#21 >> node:新替から"],
                   pad_top=40, pad_bot=8)
        await b.close()
asyncio.run(main())
