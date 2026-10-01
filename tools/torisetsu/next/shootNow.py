"""docs を手元配信（:8112）して、今の出走表とモーターを撮る。CDN は手元の React に差し替える。"""
import asyncio, sys
from playwright.async_api import async_playwright

BASE = "http://localhost:8112"
OUT = "/home/claude/next/now"
VEND = {
    "react.production.min.js": "/home/claude/vendor/react-18.2.0/umd/react.production.min.js",
    "react-dom.production.min.js": "/home/claude/vendor/react-dom-18.2.0/umd/react-dom.production.min.js",
}


async def route(r):
    u = r.request.url
    for k, v in VEND.items():
        if u.endswith(k):
            return await r.fulfill(path=v, content_type="application/javascript")
    if "localhost" not in u:
        return await r.abort()
    return await r.continue_()


async def main():
    import os
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, service_workers="block")
        await ctx.route("**/*", route)
        pg = await ctx.new_page()
        errs, bad = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 else None)
        for name in ("racers", "motor"):
            await pg.goto(BASE + "/" + name + "/", wait_until="networkidle")
            await pg.wait_for_timeout(2500)
            h = await pg.evaluate("document.documentElement.scrollHeight")
            await pg.screenshot(path=f"{OUT}/{name}Full.png", full_page=True)
            print(name, "高さ", h, "本文長", await pg.evaluate("document.body.innerText.length"))
            open(f"{OUT}/{name}Text.txt", "w", encoding="utf-8").write(
                await pg.evaluate("document.body.innerText"))
        print("4xx/5xx:", bad[:10])
        print("errors:", errs[:5])
        await b.close()

asyncio.run(main())
