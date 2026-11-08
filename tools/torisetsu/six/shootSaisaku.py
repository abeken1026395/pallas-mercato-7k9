"""トリセツの作り直し（2026-11-07）：本番（手元の docs を :8112 で出したもの）から図31枚を撮る。

使い方： SHOOT=prod python3 shootSaisaku.py [top race hl motor maint rest uranai ichimark]
  - 図には共通の枠の下のタブ（.dzf-tb）を入れない。トップの「その他」の図（figTopTabs）だけはタブを入れる
  - 時刻は図ごとに固定する（データは 2026-11-07 の main b7c8301 の写し）
"""
import asyncio, sys
sys.path.insert(0, "/home/claude/six"); sys.path.insert(0, "/home/claude")
from shootLib import *

HIDE = ".dzf-tb,.dzf-sh,body>nav.tb,.rnav{display:none!important}"
T_TOP = "2026-11-07T13:33:00+09:00"    # トップ：昼の開催が発売中、ナイターはこれから
T_RACE = "2026-11-07T17:45:00+09:00"   # 出走表：桐生（ナイター）の1R〜6Rが済み、7R（17:55）が締切10分前


async def safe(*a, **k):
    try:
        await grab(*a, **k)
    except SystemExit as e:
        print("NG", e)


async def page(b, path, at, hide=True):
    pg = await openPage(b, path, at=at)
    if hide:
        await pg.add_style_tag(content=HIDE)
        await pg.wait_for_timeout(200)
    return pg


async def top(b):
    pg = await page(b, "topI.html", T_TOP)
    await safe(pg, "figTopNav", "header.bar", "#hl",
               ["header.bar", ".cap", ".prb#0", "#hl"], pad_top=0, pad_bot=10)
    await safe(pg, "figTopKaisai", ".seg", "#chBox",
               [".seg", ".sub", "#grid >> a#0", "#offL", "#lg", "#chHead"], pad_top=8, pad_bot=8)
    await safe(pg, "figTopKensho", "text^:朝の見立ての答え合わせ#0", "details.ans-d",
               ["#tbUpd", ".ans-c.are >> .k", ".ans-c.are >> .v", ".ans-c.are >> .u", ".ans-c.are >> .bars",
                ".ntl", "details.ans-d >> summary"], pad_top=8, pad_bot=10)
    pg = await page(b, "topI.html", T_TOP, hide=False)
    await pg.click("#moreBtn"); await pg.wait_for_timeout(900)
    await safe(pg, "figTopTabs", ".sheet-in", ".tb",
               [".sheet-in >> a#0", ".sheet-in >> .sh2", ".sheet-in >> .hint", "#hikitsugi", ".tb"], pad_top=0, pad_bot=0)


async def race(b):
    pg = await page(b, "racers.html", T_RACE)
    await safe(pg, "figVenueList", ".crumb", ".venue-card#3",
               [".fortune-bar", ".date-tabs", ".venue-card#0 >> .venue-name", "→.venue-card#1 >> node:12R｜",
                ".venue-card#2 >> .venue-day", ".venue-card#3 >> .gbadge"], pad_bot=14)
    await pg.locator(".venue-card").first.click(); await pg.wait_for_timeout(1500)
    await safe(pg, "figRaceList", ".rgrid", "node:きょうの観察点",
               [".rgrid >> .rbtn#0 >> .rno", ".rgrid >> .rbtn#0 >> .rdone",
                ".rgrid >> .rbtn#8 >> .rbtn-down", ".legend-note#0", "text^:場の朝刊#0"], pad_bot=24)
    await pg.locator(".rgrid .rbtn").nth(6).click(); await pg.wait_for_timeout(1800)
    await safe(pg, "figRaceTop", ".race-head", ".race-head",
               [".race-head >> .line1", ".race-head >> .cd", ".race-head >> node:会長杯", ".race-head >> .watchbtn",
                ".race-head >> text^:公式出走表#0", ".race-head >> text^:この6艇を占う#0"])
    await safe(pg, "figRaceHead", ".chips", ".card-legend",
               [".chips >> .chip#0", ".chips >> .chip#3", "details.mido >> summary",
                ".sortbar", "details.ns#0 >> summary", "details.ns#1 >> summary", ".card-legend"])
    await safe(pg, "figBoatTop", ".boat#0", ".boat#0 >> .kmr",
               [".boat#0 >> .boat-top", ".boat#0 >> .boat-sub", ".boat#0 >> .badges",
                ".boat#0 >> .nums >> .h#0", ".boat#0 >> .nums >> .l#1", ".boat#0 >> .kinmotor", ".boat#0 >> .kmr"],
               pad_top=4)
    await safe(pg, "figBoatBottom", ".boat#0 >> details.tj", ".boat#1 >> .boat-top",
               [".boat#0 >> details.tj >> summary", ".boat#0 >> .cl10-hd", ".boat#0 >> text^:内訳#0",
                ".boat#0 >> text^:進入実績#0", ".boat#0 >> .mzBox", ".boat#0 >> text^:1号艇で出たときの決着#0",
                ".boat#0 >> text^:今節成績#0", ".boat#1 >> .boat-top"])


async def hl(b):
    pg = await page(b, "highlights.html", T_TOP)
    await pg.evaluate("document.querySelector('details.howto').open=true"); await pg.wait_for_timeout(600)
    await safe(pg, "figHlLegend", "details.howto", ".viewguide",
               [".mtr-legend#0 >> .mtr-leg-item#0", ".mtr-legend#0 >> .mtr-leg-item#3", ".sym-legend >> .jimoto",
                ".sym-legend >> .flag#0", ".sym-legend >> .up", ".sym-legend >> .bunrui#0", ".sym-legend >> .mtr-leg-item#5", ".viewguide"])
    await pg.evaluate("document.querySelector('details.howto').open=false"); await pg.wait_for_timeout(600)
    await safe(pg, "figHlCards", ".tabs", ".race#1",
               [".tabs", ".race#0 >> .rname", ".race#0 >> .deadline", ".race#0 >> .rmitate"], pad_bot=10)


async def motor(b):
    pg = await page(b, "motor.html", T_TOP)
    await safe(pg, "figMotor", "h1", "text^:▼ 残り#0",
               ["h1", "text^:各場のモーターを2連率#0", "node:最終更新", "text^:▼ このデータの見方#0", "select",
                "node:11/7時点", "node:前節いちばん出ていた機", "node:選手（級別・機力）",
                "[data-motor-row]#0", "text^:▼ 残り#0"], pad_top=6)
    await pg.evaluate("document.querySelector('[data-motor-row]').click()"); await pg.wait_for_timeout(1500)
    X = "[data-motor-row] + div >> "
    await safe(pg, "figMotorRow", "[data-motor-row]#0", X + "node:出典",
               ["[data-motor-row]#0", X + "node:新替からの成績", X + "node:時点", X + "node:節ごとの着順",
                X + "node:整備履歴", X + "node:部品交換", X + "node:もすべて見る", X + "node:出典"], pad_top=4, pad_bot=40)
    pg = await page(b, "motor.html", T_TOP)
    await safe(pg, "figMotorShingae", "node:マリンキ", "[data-motor-row]#23",
               ["node:マリンキ", "node:モーター新替", "[data-motor-row]#21", "[data-motor-row]#22 >> node:新替から"],
               pad_top=40, pad_bot=8)


async def maint(b):
    pg = await page(b, "motorMaintenance.html", T_TOP)
    await safe(pg, "figMaint", "h1", "text^:9場#0",
               ["node:記録 7/15", "text^:出走表の場と機番から#0",
                "node:直前情報は毎朝", "node:直近の交換", "node:11/6（金）", "text^:9場#0"], pad_top=8, pad_bot=12)


async def rest(b):
    pg = await page(b, "stadium.html", T_TOP)
    # 上の読み物（BGM）は図に入れない。丸は上から順に「場の行（桐生）・荒れ度（桐生）・企（戸田）」で、同じ高さに2つ置かない
    await pg.evaluate("(()=>{var e=[...document.querySelectorAll('span,b,i,small,div')].find(x=>x.childElementCount==0&&x.textContent.trim()=='企'&&x.getBoundingClientRect().height>0&&x.getBoundingClientRect().top>document.querySelector(\"button[aria-label^='戸田']\").getBoundingClientRect().top-10);e.id='shootKi'})()")
    await safe(pg, "figStadiumList", "text^:1コース 49.4%#0", "#shootKi",
               ["text^:1コース 49.4%#0", "text^:荒れ度 中#0", "#shootKi"], pad_top=30, pad_bot=24)
    await pg.locator(':text-is("桐生")').first.click(); await pg.wait_for_timeout(1500)
    await safe(pg, "figStadiumTop", "text^:1コース 49.4%#0", "node:過去に最も多く出た3連単",
               ["text^:1コース 49.4%#0", "text^:荒れ度 中#0", "node:水面特性", "node:過去に最も多く出た3連単"],
               pad_top=30, pad_bot=48)
    await safe(pg, "figStadiumDetail", "node:1号艇が1着だったレースの2着内訳", "node:何レース目か",
               ["node:1号艇が1着だったレースの2着内訳", "node:対象：1号艇", "text^:2号艇#0", "node:優勝戦の出目ランキング",
                "node:対象期間", "node:※過去に出た回数", "node:荒れるサイン"], pad_bot=16)
    pg = await page(b, "results.html", T_TOP)
    # 戸田4R（3-1-5）を撮る。夜に桐生が先頭に入るので、場は名前で選ぶ（本文の「読めること」はこのレースの数字）
    await pg.evaluate("(()=>{var v=[...document.querySelectorAll('details.venue')].find(e=>e.querySelector('summary').textContent.includes('戸田'));"
                      "v.id='shootV';v.open=true;v.querySelectorAll('details.race')[3].open=true})()")
    await pg.wait_for_timeout(800)
    R = "#shootV >> details.race#3 >> "
    await safe(pg, "figResultBoats", R + "summary", R + "table",
               [R + "summary", R + ".cond", R + ".pays", R + "thead", R + "tbody >> tr#2", R + "tbody >> tr#5"], pad_bot=10)
    pg = await page(b, "payouts.html", T_TOP)
    await safe(pg, "figPayTop", "h1", "node:全場 高配当レース",
               ["node:全24場を横断", "node:データ期間", "node:各場のR別ページ", "node:全場 高配当レース"],
               pad_top=8, pad_bot=8)
    pg = await page(b, "kensho.html", T_TOP)
    await safe(pg, "figKensho", "node:定説を、数える", "text^:386日#0",
               ["node:競艇で「そういうものだ」", "node:予想はしません", "node:検証 01",
                "node:勝負駆けは効くのか", "node:「崖っぷち", "text^:386日#0"], pad_top=30, pad_bot=40)
    pg = await page(b, "glossary.html", T_TOP)
    await safe(pg, "figGlossary", "h1", "node:全行",
               ["h1", "node:決まり手・進入", "node:収録語数", "node:この辞典について", "input", "node:公式用語", "node:全行"],
               pad_top=8, pad_bot=60)


async def players(b):
    pg = await page(b, "playersH.html", T_TOP)
    await pg.locator("text=毒島").first.click(); await pg.wait_for_timeout(1800)
    await safe(pg, "figPlayerInfo", "node:基本情報", "node:出場予定",
               ["node:基本情報", "node:今年の獲得賞金", "node:趣味：", "node:群馬県桐生市出身", "node:関係", "text^:同期の選手#0", "node:出場予定"], pad_top=8, pad_bot=30)
    await safe(pg, "figPlayerRank", "node:出場予定", "node:全選手の平均",
               ["node:出場予定", "node:公式サイトの選手ページに載っている", "node:級別の推移", "node:に初出走",
                "text^:A1 19.3年#0", "node:初出走と、級別が変わった日を見る", "node:ST0.20より遅い"], pad_top=8, pad_bot=12)
    await safe(pg, "figPlayerStats", "node:期首時点の値", "node:1着の決まり手内訳",
               ["node:期首時点の値", "text^:進入コース別#0", "node:84%", "node:2着・3着まで見る",
                "node:決まり手・前づけ", "node:1着数"], pad_top=24, pad_bot=40)


async def uranai(b):
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=DSF,
                              service_workers="block", reduced_motion="reduce", timezone_id="Asia/Tokyo", locale="ja-JP")
    await ctx.route("**/*", route)
    await ctx.add_init_script("try{localStorage.setItem('uranai_me',JSON.stringify({bd:'1990-04-01',bl:'O'}));"
                              "localStorage.setItem('uranai_motion','off')}catch(e){}")
    pg = await ctx.new_page()
    from datetime import datetime
    await pg.clock.set_fixed_time(datetime.fromisoformat(T_TOP))
    await pg.goto(BASE + "/uranai/", wait_until="networkidle"); await pg.wait_for_timeout(1500)
    await pg.add_style_tag(content=HIDE + ".kataNote{display:none!important}"); await pg.wait_for_timeout(300)
    await safe(pg, "figUranai", "h1", ".ent#1",
               ["#today", ".tabs", "#inputPanel", "#seg", ".ent#0"], pad_top=14, pad_bot=14)
    await safe(pg, "figUranaiCheck", "#checkTtl", "#howTtl",
               ["table", ".verdict", "text^:レースごとの星の推し", "#chk7", "#howTtl"], pad_top=14, pad_bot=16)
    await pg.click("#tab-shobu"); await pg.wait_for_timeout(500)
    await safe(pg, "figUranaiMine", "#mycard", "#mycard",
               ["#mycard .big", "#mycard .front .stack", "#mycard .say", "#flipbtn"], pad_top=14, pad_bot=14)
    await pg.click('#scope button[data-s="race"]')
    await pg.select_option("#pv", index=0)
    await pg.click('#rchips button[data-r="1"]'); await pg.wait_for_timeout(500)
    await safe(pg, "figUranaiRace", "#scope", ".ent#1",
               ["#scope", "#pv", "#rchips", ".starpick", ".ent#0 >> .chip.star"], pad_top=14, pad_bot=14)


async def ichimark(b):
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=DSF,
                              service_workers="block", reduced_motion="reduce", timezone_id="Asia/Tokyo", locale="ja-JP")
    await ctx.route("**/*", route)
    pg = await ctx.new_page()
    from datetime import datetime
    await pg.clock.set_fixed_time(datetime.fromisoformat(T_TOP))
    await pg.goto(BASE + "/ichimark/?d=20261107&j=01&r=7", wait_until="networkidle"); await pg.wait_for_timeout(2500)
    await pg.add_style_tag(content=HIDE + ".kataNote{display:none!important}"); await pg.wait_for_timeout(300)
    await safe(pg, "figIchimark", "#pick", "#mkc",
               ["#pick", "#main >> node:1コースが逃げる見立て", "→#main >> node:の逃げの平均",
                "#main >> node:場の平均からの動き", "#mkc"], pad_top=8, pad_bot=10)


PARTS = {"top": top, "race": race, "hl": hl, "motor": motor, "maint": maint, "rest": rest,
         "players": players, "uranai": uranai, "ichimark": ichimark}


async def main():
    which = sys.argv[1:] or list(PARTS)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--lang=ja-JP"])
        for k in which:
            print("==", k)
            await PARTS[k](b)
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())
