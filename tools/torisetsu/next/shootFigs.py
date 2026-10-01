"""今の出走表とモーターから図を撮り、番号の丸を要素の位置に自動で付ける。

各図は「切り出す範囲（上端と下端の要素）」と「番号を付ける要素の並び」で定義する。
番号の位置は要素の矩形の縦中央。上から順に並んでいることを確かめ、丸どうしが
重ならないよう最小間隔を空ける（ずれた量は表示する）。
"""
import asyncio, json, sys
from playwright.async_api import async_playwright

sys.path.insert(0, "/home/claude")
from fig import callout

BASE = "http://localhost:8112"
RAW = "/home/claude/next/now"
BOOK = "/home/claude/book"
DSF = 3
GAP = 88          # 丸の中心どうしの最小間隔（px・3倍）
VEND = {
    "react.production.min.js": "/home/claude/vendor/react-18.2.0/umd/react.production.min.js",
    "react-dom.production.min.js": "/home/claude/vendor/react-dom-18.2.0/umd/react-dom.production.min.js",
}

# 要素を探す JS。sel は CSS か "text:文字列"（その文字列を含む最小の要素）か "text^:文字列"（で始まる）
FIND = r"""
(spec)=>{
  function vis(e){const r=e.getBoundingClientRect();return r.height>0&&r.width>0;}
  function byText(root,t,starts){
    const all=[...root.querySelectorAll('*')].filter(e=>{
      if(!vis(e)) return false;
      const s=(e.innerText||'').trim(); return starts? s.startsWith(t) : s.indexOf(t)>=0;});
    all.sort((a,b)=>(a.innerText||'').length-(b.innerText||'').length);
    return all;
  }
  function one(root,s){
    let k=0; const m=s.match(/^(.*)#(\d+)$/); if(m){s=m[1];k=+m[2];}
    let list;
    if(s.startsWith('text^:')) list=byText(root,s.slice(6),true);
    else if(s.startsWith('text:')) list=byText(root,s.slice(5),false);
    else list=[...root.querySelectorAll(s)].filter(vis);
    return list[k]||null;
  }
  function nodeRect(root,t){
    const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    let n; while((n=w.nextNode())){ if(n.nodeValue.indexOf(t)>=0){
      const rg=document.createRange(); rg.selectNodeContents(n); const r=rg.getBoundingClientRect();
      if(r.height>0) return r; } }
    return null;
  }
  function find(s){
    let el=document.body; const parts=s.split('>>').map(x=>x.trim());
    for(let i=0;i<parts.length;i++){
      const part=parts[i];
      if(part.startsWith('node:')){ const r=nodeRect(el,part.slice(5)); if(!r) return null;
        return {top:r.top+scrollY,bottom:r.bottom+scrollY,mid:(r.top+r.bottom)/2+scrollY}; }
      el=one(el,part); if(!el) return null; }
    const r=el.getBoundingClientRect();
    return {top:r.top+scrollY,bottom:r.bottom+scrollY,mid:(r.top+r.bottom)/2+scrollY};
  }
  const out={};
  for(const key in spec){ out[key]=Array.isArray(spec[key])? spec[key].map(find) : find(spec[key]); }
  return out;
}
"""


async def route(r):
    u = r.request.url
    for k, v in VEND.items():
        if u.endswith(k):
            return await r.fulfill(path=v, content_type="application/javascript")
    if "localhost" not in u:
        return await r.abort()
    return await r.continue_()


async def grab(pg, name, top, bottom, marks, pad_top=10, pad_bot=12, max_h=None):
    spec = {"top": top, "bottom": bottom, "marks": [m for m in marks]}
    got = await pg.evaluate(FIND, spec)
    if not got["top"] or not got["bottom"]:
        raise SystemExit(f"{name}: 範囲の要素が見つからない {got['top']} {got['bottom']}")
    y0 = got["top"]["top"] - pad_top
    y1 = got["bottom"]["bottom"] + pad_bot
    if max_h:
        y1 = min(y1, y0 + max_h)
    rows = []
    for m, g in zip(marks, got["marks"]):
        if not g:
            raise SystemExit(f"{name}: 番号の要素が見つからない {m}")
        rows.append((g["mid"] - y0) * DSF)
    # 上から順か
    for a, b in zip(rows, rows[1:]):
        if b <= a:
            raise SystemExit(f"{name}: 番号の順が上から順になっていない {rows}")
    # 重なりを空ける
    fixed, shift = [], []
    for y in rows:
        if fixed and y - fixed[-1] < GAP:
            shift.append(round(fixed[-1] + GAP - y))
            y = fixed[-1] + GAP
        else:
            shift.append(0)
        fixed.append(y)
    await pg.evaluate("window.scrollTo(0,0)")
    raw = f"{RAW}/raw_{name}.png"
    await pg.screenshot(path=raw, full_page=True,
                        clip={"x": 0, "y": y0, "width": 390, "height": y1 - y0})
    size = callout(raw, f"{BOOK}/{name}.png", [round(y) for y in fixed])
    print(f"{name}: 高さ{round((y1-y0)*DSF)}px 丸{len(fixed)}個 ずらし{shift} → {size}")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=DSF, service_workers="block")
        await ctx.route("**/*", route)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        # ── 出走表：場の一覧
        await pg.goto(BASE + "/racers/", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        await grab(pg, "figVenueList", "text^:場を選択", "node:12R｜15:24",
                   ["text^:今日の運勢", "node:10/01(木)", "text^:江戸川#0", "text^:マスターズ#0",
                    "node:12R｜10:55", "text^:２日目#0"], pad_bot=22,
                   max_h=None)

        # ── 出走表：レース画面
        await pg.get_by_text("蒲郡", exact=True).first.click()
        await pg.wait_for_timeout(1200)
        await grab(pg, "figRaceList", ".rgrid", "text^:📝 観戦記",
                   [".rgrid >> .rbtn#0 >> .rno", ".rgrid >> .rbtn#0 >> .rdone",
                    ".rgrid >> .rbtn#8 >> .rbtn-down", ".legend-note#0", "text^:📝 観戦記"],
                   pad_bot=70)
        await pg.get_by_text("8R", exact=True).first.click()
        await pg.wait_for_timeout(1800)
        await grab(pg, "figRaceTop", ".race-head", ".race-head",
                   [".race-head >> .line1", ".race-head >> .cd", ".race-head >> text^:「いい風吹け」",
                    ".race-head >> .watchbtn", ".race-head >> .offlink-card"])
        await grab(pg, "figRaceHead", ".chips", ".card-legend",
                   [".chips >> .chip#0", ".chips >> .chip#3", "details.mido >> summary",
                    ".sortbar", "details.ns#0 >> summary", "details.ns#1 >> summary", ".card-legend"])
        await grab(pg, "figBoatTop", ".boat#0", ".boat#0 >> .kmr",
                   [".boat#0 >> .boat-top", ".boat#0 >> .boat-sub", ".boat#0 >> .badges",
                    ".boat#0 >> .nums >> .h#0", ".boat#0 >> .nums >> .l#1", ".boat#0 >> .kinmotor", ".boat#0 >> .kmr"],
                   pad_top=4)
        await grab(pg, "figBoatBottom", ".boat#0 >> details.tj", ".boat#1 >> .boat-top",
                   [".boat#0 >> details.tj >> summary", ".boat#0 >> .cl10-hd", ".boat#0 >> text^:内訳#0",
                    ".boat#0 >> text^:1号艇で出たときの決着#0", ".boat#0 >> text^:今節成績#0", ".boat#1 >> .boat-top"])

        # ── モーター：上
        await pg.goto(BASE + "/motor/", wait_until="networkidle")
        await pg.wait_for_timeout(2000)
        await grab(pg, "figMotor", "text^:BOATRACE モーター成績", "text^:▼ 残り45機を見る#0",
                   ["text^:BOATRACE モーター成績", "text^:超抜 ＝#0", "text^:各場は上位3機",
                    "text^:▼ このデータの見方", "select", "node:桐生", "[data-motor-row]#0",
                    "text^:▼ 残り45機を見る#0"])
        # ── モーター：行を開いたところ
        await pg.evaluate("document.querySelector('[data-motor-row]').click()")
        await pg.wait_for_timeout(1800)
        await grab(pg, "figMotorRow", "[data-motor-row]#0", "text^:出典：boatrace.jp 公式 直前情報#0",
                   ["[data-motor-row]#0", "text^:モーター新替 2025/12/27#0", "text^:公式 9/25時点#0",
                    "text^:整備履歴#0", "text^:9/24 8R#0", "text^:残り47走#0",
                    "text^:出典：boatrace.jp 公式 直前情報#0"])
        # ── モーター：新替から5節の場
        await pg.goto(BASE + "/motor/", wait_until="networkidle")
        await pg.wait_for_timeout(2000)
        await grab(pg, "figMotorShingae", "text^:唐津#0", "text^:高橋　嗣穏#0",
                   ["text^:唐津#0", "text^:日刊スポーツ杯#0", "text^:モーター新替 2026/9/16#0",
                    "text^:赤井#0", "text^:11走#0"], pad_bot=44)
        print("errors:", errs[:3])
        await b.close()

asyncio.run(main())
