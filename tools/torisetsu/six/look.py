"""第6版のページを手元で開き、全体を撮る（図の設計用）。python3 six/look.py ページ [クリックのセレクタ...]"""
import asyncio, sys
from playwright.async_api import async_playwright
BASE="http://localhost:8112/next/kansei6/"
VEND={"react.production.min.js":"/home/claude/vendor/react-18.2.0/umd/react.production.min.js","react-dom.production.min.js":"/home/claude/vendor/react-dom-18.2.0/umd/react-dom.production.min.js","babel.min.js":"/tmp/claude-0/-home-claude-pallas-mercato-7k9/e7714348-ef16-52b4-857a-bc722237461c/scratchpad/npm/x_babel-standalone-7.23.9/package/babel.min.js"}
async def route(r):
    u=r.request.url
    for k,v in VEND.items():
        if u.endswith(k): return await r.fulfill(path=v,content_type="application/javascript")
    if "localhost" not in u: return await r.abort()
    return await r.continue_()
async def main():
    page=sys.argv[1]; out=sys.argv[2]
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=1,service_workers="block",reduced_motion="reduce")
        await ctx.route("**/*",route)
        pg=await ctx.new_page()
        url = page if page.startswith("http") else (("http://localhost:8112/next/"+page) if page.startswith("top") or page.startswith("players") else BASE+page)
        await pg.goto(url,wait_until="networkidle"); await pg.wait_for_timeout(2000)
        await pg.add_style_tag(content=".kataNote{display:none!important}")
        for c in sys.argv[3:]:
            if c.startswith("js:"): await pg.evaluate(c[3:])
            else: await pg.locator(c).first.click()
            await pg.wait_for_timeout(1500)
        await pg.screenshot(path=out,full_page=True)
        await b.close()
asyncio.run(main())
