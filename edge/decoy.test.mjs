// 囮の検収をローカルで再現する（node --test edge/）。
// 実ファイル docs/ を本物として middleware に通し、名乗り別の返り値を確かめる。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { onRequest } from "../functions/_middleware.js";
import { NOTICE_TEXT, decoyRacersCsv } from "./decoy.mjs";

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

test("普通のブラウザ：本物がそのまま出る", async () => {
  for (const p of PATHS) {
    const a = await get(p, BROWSER);
    assert.equal(a.text, a.real, p);
  }
});

test("通告は中盤（先頭ではない）", async () => {
  for (const p of ["/racers/", "/players/card.html"]) {
    const a = await get(p, "Claude-User/1.0");
    const at = a.text.indexOf(NOTICE_TEXT);
    const body = a.text.search(/<body[^>]*>/i);
    assert.ok(at > body + 200, `${p} 通告が先頭寄り`);
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
  for (const row of Object.values(JSON.parse(a.text)))
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
