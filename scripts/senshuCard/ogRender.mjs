// 選手カードのサムネ（OGP 1200x630）を、カード本体の名札の描き方（card.html の scPlate）でそのまま描き出す。
// カードの見た目を変えれば、次の作り直しでサムネも同じになる（別に描き方を持たない）。
//
// 使い方: node scripts/senshuCard/ogRender.mjs <docs の場所> <登番の一覧ファイル（1行1人）> <出力フォルダ>
// 出力: <出力フォルダ>/<登番>.png（カードが描いたままの PNG。減色は sharePages.py が行う）
// 必要なもの: playwright（npm）と Chromium
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const [docs, listFile, outDir] = process.argv.slice(2);
if (!docs || !listFile || !outDir) { console.error("引数: <docs> <list> <outDir>"); process.exit(2); }
const list = fs.readFileSync(listFile, "utf-8").split(/\s+/).filter(Boolean);
fs.mkdirSync(outDir, { recursive: true });

const TYPES = { ".html": "text/html; charset=utf-8", ".json": "application/json", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml", ".woff2": "font/woff2" };
const root = path.resolve(docs);
const server = http.createServer((req, res) => {
  const u = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const f = path.join(root, u);
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { "content-type": TYPES[path.extname(f)] || "application/octet-stream" });
  fs.createReadStream(f).pipe(res);
});
await new Promise(r => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

const browser = await chromium.launch();
let bad = 0;
try {
  const page = await browser.newPage();
  // 外部（解析・フォント配信）には出さない。サムネはキルゴUの字形と、等幅の級表示だけで描く
  await page.route(u => !u.href.startsWith(`http://127.0.0.1:${port}/`), r => r.abort());
  await page.goto(`http://127.0.0.1:${port}/players/card.html?toban=${list[0] || "4238"}`);
  await page.waitForFunction(() => typeof D !== "undefined" && D && D.players && typeof K !== "undefined" && K && typeof scPlate === "function", null, { timeout: 60000 });
  for (let i = 0; i < list.length; i += 50) {
    const part = list.slice(i, i + 50);
    const got = await page.evaluate(async (part) => {
      const out = {}, pal = scPal(false), W = 1200, H = 630, S = 1.9, PH = 576;
      for (const no of part) {
        await loadP(no);
        const P = D.players[no];
        if (!P) { out[no] = null; continue; }
        const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
        const c = cv.getContext("2d");
        c.fillStyle = "#0d0d0d"; c.fillRect(0, 0, W, H);
        // 名札の中身（級・名前・二つ名）を縦の真ん中に寄せる
        const oy = Math.round(P.tag ? 70 : 95);
        scPlate(c, P, no, 0, 0, W, PH, S, pal, oy);
        out[no] = cv.toDataURL("image/png").split(",")[1];
      }
      return out;
    }, part);
    for (const [no, b64] of Object.entries(got)) {
      if (!b64) { bad++; console.error("描けない:", no); continue; }
      fs.writeFileSync(path.join(outDir, no + ".png"), Buffer.from(b64, "base64"));
    }
  }
} finally {
  await browser.close();
  server.close();
}
console.log(`描いた ${list.length - bad} 人`);
process.exit(bad ? 1 : 0);
