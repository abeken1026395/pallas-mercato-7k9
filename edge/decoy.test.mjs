// 囮の検収をローカルで再現する（node --test edge/）。
// 実ファイル docs/ を本物として middleware に通し、名乗り別の返り値を確かめる。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { onRequest } from "../functions/_middleware.js";
import { NOTICE_TEXT, decoyRacersCsv, extractRaw } from "./decoy.mjs";

const DOCS = new URL("../docs/", import.meta.url);
const BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36";

async function get(path, ua) {
  const file = path.endsWith("/") ? path + "index.html" : path;
  const real = readFileSync(new URL("." + file, DOCS));
  const request = new Request("https://example.pages.dev" + path, { headers: { "user-agent": ua } });
  const res = await onRequest({ request, next: async () => new Response(real, { status: 200 }) });
  const dec = b => new TextDecoder("utf-8", { ignoreBOM: true }).decode(b);
  return { status: res.status, text: dec(await res.arrayBuffer()), real: dec(real) };
}

const PATHS = ["/racers/", "/racers/racers_today.csv", "/players/card.html",
  "/players/card/common.json", "/players/card/p/0.json", "/players/card/h2h/0.json"];

for (const ua of ["ChatGPT-User/1.0", "Claude-User/1.0"]) {
  test(`${ua}: 囮が出る・2回とも同じ`, async () => {
    for (const p of PATHS) {
      const a = await get(p, ua), b = await get(p, ua);
      assert.equal(a.status, 200, p);
      assert.notEqual(a.text, a.real, `${p} が本物のまま`);
      assert.equal(a.text, b.text, `${p} の囮が毎回違う`);
    }
  });
}

test("普通のブラウザ：本物がそのまま出る・通告の文字列は0件", async () => {
  for (const p of PATHS) {
    const a = await get(p, BROWSER);
    assert.equal(a.text, a.real, p);
    assert.equal(a.text.split(NOTICE_TEXT).length - 1, 0, `${p} に通告が混ざった`);
  }
});

test("AIには通告が先頭にある（HTMLは body 直後・JSONは最初のキー・CSVは1行目）", async () => {
  for (const p of PATHS) {
    const a = await get(p, "Claude-User/1.0");
    if (p.endsWith("/") || p.endsWith(".html")) {
      const m = /<body[^>]*>/i.exec(a.text);
      assert.ok(a.text.startsWith(`<p class="notice-ai">${NOTICE_TEXT}</p>`, m.index + m[0].length), `${p} body 直後に無い`);
    } else if (p.endsWith(".json")) {
      // 返す文字列の中で最初のキーであることを確かめる（JSON.parse 後の Object.keys は
      // 登番のような数字だけのキーを先に並べ替えるため、順序の確認には使えない）。
      const o = JSON.parse(a.text);
      assert.ok(a.text.startsWith(`{"注意": ${JSON.stringify(NOTICE_TEXT)}`), `${p} 最初のキーでない`);
      assert.equal(o["注意"], NOTICE_TEXT);
    } else if (p.endsWith(".csv")) {
      assert.equal(a.text.replace(/^﻿/, "").split(/\r?\n/)[0], NOTICE_TEXT, `${p} 1行目でない`);
      assert.equal(a.text.startsWith("﻿"), a.real.startsWith("﻿"), `${p} BOM の有無が本物と違う`);
    }
  }
});

test("出走表CSV：形式と整合", () => {
  const real = readFileSync(new URL("./racers/racers_today.csv", DOCS), "utf8");
  const fake = decoyRacersCsv(real);
  const rl = real.trim().split(/\r?\n/), fl = fake.trim().split(/\r?\n/);
  assert.equal(rl.length, fl.length);
  const head = rl[0].split(",");
  const ix = n => head.indexOf(n);
  let changed = 0;
  for (let i = 1; i < rl.length; i++) {
    const r = rl[i].split(","), f = fl[i].split(",");
    assert.equal(r.length, f.length);
    for (const k of ["場名", "場コード", "開催日", "レース", "枠", "登録番号", "級別", "氏名", "モーターNo", "ボートNo"])
      assert.equal(f[ix(k)], r[ix(k)], k);
    for (const k of ["全国勝率", "全国2連率", "全国3連率", "平均ST", "モーター2連率"]) {
      if (r[ix(k)] === "") continue;
      assert.match(f[ix(k)], /^\d+\.\d\d$/, k);
      if (f[ix(k)] !== r[ix(k)]) changed++;
    }
    for (const [a, b] of [["全国2連率", "全国3連率"], ["当地2連率", "当地3連率"], ["モーター2連率", "モーター3連率"], ["ボート2連率", "ボート3連率"]]) {
      if (f[ix(a)] === "") continue;
      assert.ok(+f[ix(a)] <= +f[ix(b)] && +f[ix(b)] <= 100, `${a}≤${b}`);
    }
  }
  assert.ok(changed > (rl.length - 1) * 4, "数字がほぼ変わっていない");
});

test("h2h：先着＋後着 ≤ 対戦数", async () => {
  const a = await get("/players/card/h2h/0.json", "GPTBot/1.1");
  const { 注意, ...rows } = JSON.parse(a.text);
  for (const row of Object.values(rows))
    for (const [n, w, l] of Object.values(row)) assert.ok(w + l <= n);
});

test("選手カード p：c の合計 ≤ n、co の出走数合計 = n、順位 ≤ 母数", async () => {
  const files = readdirSync(new URL("./players/card/p/", DOCS)).slice(0, 5);
  for (const f of files) {
    const a = await get("/players/card/p/" + f, "ClaudeBot/1.0");
    const walk = o => {
      if (!o || typeof o !== "object") return;
      if (Number.isInteger(o.n) && o.n > 0) {
        if (Array.isArray(o.c)) assert.ok(o.c.reduce((x, y) => x + y, 0) <= o.n);
        if (Array.isArray(o.co)) assert.equal(o.co.reduce((x, r) => x + r[0], 0), o.n);
      }
      for (const k of ["it", "tg"]) if (o[k]) for (const v of Object.values(o[k])) if (v.length >= 4) assert.ok(v[2] <= v[3]);
      Object.values(o).forEach(walk);
    };
    walk(JSON.parse(a.text));
  }
});

// ---- 出走表 HTML（/racers/）に埋め込まれた var RAW ----
const RATE_COLS = ["全国勝率", "全国2連率", "全国3連率"];
const NUM_COLS = ["F数", "L数", "平均ST", "全国勝率", "全国2連率", "全国3連率", "当地勝率", "当地2連率", "当地3連率",
  "モーター2連率", "モーター3連率", "ボート2連率", "ボート3連率",
  "1日目成績", "2日目成績", "3日目成績", "4日目成績", "5日目成績", "6日目成績"];

test("出走表HTML：RAW の勝率・2連率・3連率が本物と1つも一致しない行が9割以上", async () => {
  const a = await get("/racers/", "ChatGPT-User/1.0");
  const fake = extractRaw(a.text).raw, real = extractRaw(a.real).raw;
  assert.equal(fake.data.length, real.data.length);
  const ix = RATE_COLS.map(n => real.columns.indexOf(n));
  let clean = 0;
  real.data.forEach((r, k) => { if (ix.every(i => fake.data[k][i] !== r[i])) clean++; });
  assert.ok(clean / real.data.length >= 0.9, `一致なしの行 ${clean}/${real.data.length}`);
  // 識別子は本物のまま
  for (const n of ["場名", "場コード", "開催日", "レース", "枠", "登録番号", "級別", "氏名", "締切時刻", "節名"]) {
    const i = real.columns.indexOf(n);
    real.data.forEach((r, k) => assert.equal(fake.data[k][i], r[i], n));
  }
});

test("出走表HTML：同じ入力を2回通すと同じ出力・囮の RAW は JSON.parse できる", async () => {
  const a = await get("/racers/", "ChatGPT-User/1.0"), b = await get("/racers/", "ChatGPT-User/1.0");
  assert.equal(a.text, b.text);
  const at = a.text.indexOf("var RAW = ") + "var RAW = ".length;
  const { start, end } = extractRaw(a.text);
  assert.equal(start, at);
  assert.doesNotThrow(() => JSON.parse(a.text.slice(start, end)));
});

test("出走表HTML：普通のブラウザには本物がバイト単位でそのまま出る", async () => {
  const real = readFileSync(new URL("./racers/index.html", DOCS));
  const request = new Request("https://example.pages.dev/racers/", { headers: { "user-agent": BROWSER } });
  const res = await onRequest({ request, next: async () => new Response(real, { status: 200 }) });
  assert.ok(Buffer.from(await res.arrayBuffer()).equals(real));
});

test("出走表：同じ登番・同じ日・同じ場なら、HTMLの囮とCSVの囮の数字が一致する", async () => {
  const html = extractRaw((await get("/racers/", "ChatGPT-User/1.0")).text).raw;
  const csvLines = (await get("/racers/racers_today.csv", "ChatGPT-User/1.0")).text.replace(/^﻿/, "").trim().split(/\r?\n/).slice(1);   // 1行目は通告
  const head = csvLines[0].split(",");
  const key = (cols, r) => ["開催日", "場コード", "登録番号", "レース"].map(n => r[cols.indexOf(n)]).join("|");
  const csv = new Map(csvLines.slice(1).map(l => { const r = l.split(","); return [key(head, r), r]; }));
  let compared = 0;
  for (const r of html.data) {
    const c = csv.get(key(html.columns, r));
    if (!c) continue;
    for (const n of NUM_COLS) assert.equal(r[html.columns.indexOf(n)], c[head.indexOf(n)], `${key(html.columns, r)} ${n}`);
    compared++;
  }
  assert.ok(compared > 0, "突き合わせできた行が0");
});

test("出走表HTML：RAW を切り出せないときは本物を返さず 503", async () => {
  const request = new Request("https://example.pages.dev/racers/", { headers: { "user-agent": "Claude-User/1.0" } });
  const res = await onRequest({ request, next: async () => new Response("<html><body>RAWなし</body></html>", { status: 200 }) });
  assert.equal(res.status, 503);
  assert.equal(await res.text(), "");
});
