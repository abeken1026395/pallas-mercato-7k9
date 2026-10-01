import sys, asyncio
from playwright.async_api import async_playwright

URL = "http://localhost:8099/index.html"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = await b.new_page(viewport={"width": 390, "height": 844},
                              device_scale_factor=2)
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(URL, wait_until="load")
        await pg.wait_for_timeout(1600)
        await pg.screenshot(path="shot1_hero.png")

        # 第1部の先頭
        await pg.evaluate("document.getElementById('s11').scrollIntoView()")
        await pg.wait_for_timeout(400)
        await pg.screenshot(path="shot2_step1.png")

        # 第2部：記号の表
        await pg.evaluate("document.getElementById('s21').scrollIntoView()")
        await pg.wait_for_timeout(300)
        await pg.mouse.wheel(0, 900)
        await pg.wait_for_timeout(300)
        await pg.screenshot(path="shot3_sym.png")

        # Q&A を2つ開く
        await pg.evaluate("document.getElementById('s22').scrollIntoView()")
        await pg.wait_for_timeout(200)
        await pg.evaluate("document.querySelectorAll('.sy .q')[0].click();"
                          "document.querySelectorAll('.sy .q')[1].click()")
        await pg.wait_for_timeout(500)
        await pg.screenshot(path="shot4_qa.png")

        # 第3部：写真と番号
        await pg.evaluate("document.getElementById('g01').scrollIntoView()")
        await pg.wait_for_timeout(300)
        await pg.mouse.wheel(0, 260)
        await pg.evaluate("document.querySelectorAll('ol.lg')[0].querySelectorAll('li')[2].click()")
        await pg.wait_for_timeout(400)
        await pg.screenshot(path="shot5_fig.png")

        # もくじ・さがす
        await pg.evaluate("document.getElementById('bToc').click()")
        await pg.wait_for_timeout(600)
        await pg.screenshot(path="shot6_toc.png")
        await pg.fill("#srch", "N少")
        await pg.wait_for_timeout(400)
        await pg.screenshot(path="shot7_search.png")

        h = await pg.evaluate("document.documentElement.scrollHeight")
        print("errors:", errs)
        print("height:", h)
        await b.close()

asyncio.run(main())
