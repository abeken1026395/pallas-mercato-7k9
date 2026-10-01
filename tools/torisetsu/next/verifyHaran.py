import asyncio, json
from playwright.async_api import async_playwright

async def hl_snapshot(ctx, port):
    """見どころの全タブ・全日付の札と本文を集める"""
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"http://localhost:{port}/highlights/", wait_until="networkidle")
    await pg.wait_for_timeout(2500)
    out = {}
    days = await pg.evaluate("[...document.querySelectorAll('.dtab,.daytab,[data-d]')].map(e=>e.getAttribute('data-d')||e.textContent.trim())")
    views = await pg.evaluate("[...document.querySelectorAll('.tab[data-v]')].map(e=>e.getAttribute('data-v'))")
    out["views"] = views; out["days"] = days
    for v in views:
        await pg.evaluate(f"document.querySelector('.tab[data-v=\"{v}\"]').click()")
        await pg.wait_for_timeout(1200)
        out[v] = await pg.evaluate("""({badges:[...document.querySelectorAll('.badge')].map(e=>e.textContent),
                                         text:(document.querySelector('#list')||document.body).innerText})""")
    await pg.close()
    return out, errs

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
        await ctx.route("**/*", lambda r: r.abort() if "localhost" not in r.request.url else r.continue_())

        o, oe = await hl_snapshot(ctx, 8121)
        n, ne = await hl_snapshot(ctx, 8122)
        print("見どころ タブ:", o["views"], "／ 日付タブ候補:", o["days"][:6])
        for v in o["views"]:
            same_b = o[v]["badges"] == n[v]["badges"]
            same_t = o[v]["text"] == n[v]["text"]
            print(f"  {v:6s} 札 {len(o[v]['badges']):3d}個 旧新一致:{same_b}  本文一致:{same_t}")
        print("  errors 旧:", oe[:2], "新:", ne[:2])

        # 出走表：全レースの①着外を、highlights.json から同じ式で出した値と照合
        hj = json.load(open("/tmp/claude-0/-home-claude-pallas-mercato-7k9/bbeb2fbd-4a51-5bd1-b2a7-eba33ed4f98698/scratchpad/newDocs/docs/highlights/highlights.json"))
        CUT = [0, 0.4, 0.7, 1.0, 1.3]
        def lv(r):
            v = r.get("波乱指数")
            if not isinstance(v, (int, float)): return r.get("波乱")
            k = 1
            for c in CUT:
                if v >= c: k += 1
            return k
        exp = {}
        for r in hj["レース"]:
            exp[f'{int(r["場コード"]):02d}_{int(str(r["レース"]).rstrip("R"))}R'] = lv(r)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto("http://localhost:8122/racers/", wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        got = await pg.evaluate("(()=>{const o={};for(const k in HL){o[k]=haranLvOf(HL[k].hidx,HL[k].haran);}return o;})()")
        common = sorted(set(exp) & set(got))
        mism = [(k, exp[k], got[k]) for k in common if exp[k] != got[k]]
        print(f"出走表 HL {len(got)}件 / highlights {len(exp)}件 / 突き合わせ {len(common)}件 / 不一致 {len(mism)}件", mism[:5])
        # 画面のチップの文字（蒲郡8R）
        await pg.get_by_text("蒲郡", exact=True).first.click(); await pg.wait_for_timeout(800)
        await pg.get_by_text("8R", exact=True).first.click(); await pg.wait_for_timeout(1500)
        chips = await pg.evaluate("[...document.querySelectorAll('.chips .chip')].map(e=>e.textContent)")
        cap = await pg.evaluate("(document.querySelector('.shu-cap')||{}).textContent")
        print("蒲郡8R チップ:", chips, "／ 期待値:", exp.get("07_8R"), "／ 今節成績の見出し:", cap)
        print("errors:", errs[:3])
        await b.close()

asyncio.run(main())
