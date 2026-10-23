"""第6版の24場・結果・万舟・検証・用語・整備・選手図鑑から図を撮る。"""
import asyncio, sys
sys.path.insert(0, "/home/claude/six"); sys.path.insert(0, "/home/claude")
from shootLib import *
async def safe(*a, **k):
    try: await grab(*a, **k)
    except SystemExit as e: print("NG", e)
async def main():
    which = set(sys.argv[1:])
    async with async_playwright() as p:
        b = await p.chromium.launch()
        if not which or "stadium" in which:
            pg = await openPage(b, "stadium.html")
            await safe(pg, "figStadiumList", "node:締切前に", "node:江戸川",
                       ["text^:1コース 43.1%#0", "button[aria-label^='戸田']", "text^:荒れ度 高#0"], pad_top=8, pad_bot=30)
            await pg.locator(':text-is("桐生")').first.click(); await pg.wait_for_timeout(1500)
            await safe(pg, "figStadiumTop", "node:締切前に", "node:過去に最も多く出た3連単",
                       ["node:締切前に", "text^:1コース 49.4%#0", "text^:荒れ度 中#0", "node:水面特性", "node:過去に最も多く出た3連単"], pad_top=8, pad_bot=16)
            await safe(pg, "figStadiumDetail", "node:1号艇が1着だったレースの2着内訳", "node:荒れるサイン",
                       ["node:1号艇が1着だったレースの2着内訳", "node:対象：1号艇", "text^:2号艇#0", "node:優勝戦の出目ランキング",
                        "node:対象期間", "node:※過去に出た回数", "node:荒れるサイン"], pad_bot=200)
        if not which or "results" in which:
            pg = await openPage(b, "results.html")
            await pg.evaluate("document.querySelector('details.venue').open=true"); await pg.wait_for_timeout(500)
            await pg.evaluate("document.querySelectorAll('details.venue')[0].querySelectorAll('details.race')[3].open=true"); await pg.wait_for_timeout(800)
            R = "details.venue#0 >> details.race#3 >> "
            await safe(pg, "figResultBoats", R + "summary", R + "table",
                       [R + "summary", R + ".cond", R + ".pays", R + "thead", R + "tbody >> tr#1", R + "tbody >> tr#5"], pad_bot=10)
        if not which or "payouts" in which:
            pg = await openPage(b, "payouts.html")
            await safe(pg, "figPayTop", "h1", "node:全場 高配当レース",
                       ["node:全24場を横断", "node:全24場を横断", "node:データ期間", "node:各場のR別ページ", "node:全場 高配当レース"], pad_top=8, pad_bot=8)
        if not which or "kensho" in which:
            pg = await openPage(b, "kensho.html")
            await safe(pg, "figKensho", "node:定説を、数える", "text^:386日#0",
                       ["node:競艇で「そういうものだ」", "node:予想はしません", "node:検証 01",
                        "node:勝負駆けは効くのか", "node:「崖っぷち", "text^:386日#0"], pad_top=30, pad_bot=40)
        if not which or "glossary" in which:
            pg = await openPage(b, "glossary.html")
            await safe(pg, "figGlossary", "h1", "node:全行",
                       ["h1", "node:決まり手・進入", "node:収録語数", "node:この辞典について", "input", "node:公式用語", "node:全行"], pad_top=8, pad_bot=60)
        if not which or "maint" in which:
            pg = await openPage(b, "motorMaintenance.html")
            await safe(pg, "figMaint", "h1", "text^:11場#0",
                       ["node:記録 7/15", "text^:出走表の場と機番から#0", "text^:出走表の場と機番から#0 >> node:交換は場の記録", "node:直前情報は毎朝",
                        "node:直近の交換", "node:10/22（木）", "text^:11場#0"], pad_top=8, pad_bot=12)
        if not which or "players" in which:
            pg = await openPage(b, "playersH.html")
            await pg.locator("text=毒島").first.click(); await pg.wait_for_timeout(1800)
            await safe(pg, "figPlayerInfo", "node:基本情報", "node:出場予定",
                       ["node:基本情報", "node:今年の獲得賞金", "node:趣味：", "node:群馬県桐生市出身", "node:師匠", "text^:同期の選手#0", "node:出場予定"], pad_top=8, pad_bot=12)
            await safe(pg, "figPlayerRank", "node:出場予定", "node:全選手の平均",
                       ["node:出場予定", "node:公式サイトの選手ページに載っている", "node:級別の推移", "node:に初出走",
                        "text^:A1 19.3年#0", "node:初出走と、級別が変わった日を見る", "node:ST0.20より遅い"], pad_top=8, pad_bot=12)
            await safe(pg, "figPlayerStats", "node:期首時点の値", "node:1着の決まり手内訳",
                       ["node:期首時点の値", "text^:進入コース別#0", "node:84%", "text^:10走#0", "node:2着・3着まで見る",
                        "node:直近6ヶ月", "node:1着数"], pad_top=24, pad_bot=12)
        await b.close()
asyncio.run(main())
