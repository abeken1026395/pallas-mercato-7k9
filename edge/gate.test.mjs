// node --test edge/gate.test.mjs
// 人間確認の関門：印が無ければページは確認画面・データは403、印があれば本物、合図があれば本物、鍵が無ければ関門は開いたまま。
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../functions/_middleware.js";
import { makePass, validPass, isOpenPath, GATE_COOKIE } from "./gate.mjs";

const BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const REAL = "本物の中身 全国勝率 6.12";
const ENV = { DZ_TS_SITEKEY: "0xSITE", DZ_TS_SECRET: "sec", DZ_GATE_SIGN: "signkey", DZ_GATE_KEY: "gatekey" };

async function get(path, { env = ENV, ua = BROWSER, cookie, key, method = "GET", body } = {}) {
  let touched = false;
  const headers = { "user-agent": ua, "accept-language": "ja-JP,ja;q=0.9", "cf-connecting-ip": "203.0.113.5" };
  if (cookie) headers.cookie = cookie;
  if (key) headers["x-dz-key"] = key;
  const init = { method, headers };
  if (body) { init.body = body; headers["content-type"] = "application/x-www-form-urlencoded"; }
  const request = new Request("https://example.pages.dev" + path, init);
  const res = await onRequest({ request, env, next: async () => { touched = true; return new Response(REAL, { status: 200 }); } });
  return { status: res.status, text: await res.text(), touched, setCookie: res.headers.get("set-cookie") || "" };
}

const PAGES = ["/", "/glossary/", "/kensho/players/", "/results/", "/racers/", "/stadium/index.html"];
const DATA = ["/data/weather.json", "/results/20261122.json", "/racers/racers_today.csv", "/racers/entryIndex.json"];

test("印が無い人：ページは確認画面（本物に触れない）、データは403", async () => {
  for (const p of PAGES) {
    const r = await get(p);
    assert.equal(r.status, 403, p); assert.equal(r.touched, false, p);
    assert.ok(r.text.includes("cf-turnstile") && r.text.includes("0xSITE"), p);
    assert.ok(!r.text.includes(REAL));
  }
  for (const p of DATA) {
    const r = await get(p);
    assert.equal(r.status, 403, p); assert.equal(r.touched, false, p);
  }
});

test("正しい印がある人は本物。偽の印・期限切れは止める", async () => {
  const pass = await makePass("signkey");
  for (const p of [...PAGES, ...DATA]) {
    const r = await get(p, { cookie: `${GATE_COOKIE}=${pass}; dzv=0123456789abcdef` });
    assert.equal(r.status, 200, p); assert.equal(r.text, REAL);
  }
  const forged = pass.slice(0, -1) + (pass.endsWith("0") ? "1" : "0");
  assert.equal((await get("/", { cookie: `${GATE_COOKIE}=${forged}` })).status, 403);
  const old = await makePass("signkey", Date.now() - 40 * 86400000);
  assert.equal(await validPass("signkey", old), false);
  assert.equal(await validPass("otherkey", pass), false);
});

test("秘密の合図（配信WFの確認・通知の送り役）は本物。違う合図は止める", async () => {
  assert.equal((await get("/racers/entryIndex.json", { key: "gatekey" })).text, REAL);
  assert.equal((await get("/", { key: "gatekey" })).text, REAL);
  assert.equal((await get("/", { key: "wrong" })).status, 403);
});

test("関門の外：告知の入口・カード画像・見た目の部品・通知の受け口", async () => {
  for (const p of ["/in/line/shogo/", "/ogpShogo.png", "/assets/guard.js", "/api/now", "/sw.js", "/robots.txt", "/kiyaku/"]) {
    assert.ok(isOpenPath(p), p);
    const r = await get(p);
    assert.equal(r.status, 200, p); assert.equal(r.text, REAL);
  }
  assert.ok(!isOpenPath("/data/weather.json")); assert.ok(!isOpenPath("/index.html"));
});

test("鍵が1つでも無いときは関門を開けたまま（読者を締め出さない）", async () => {
  for (const drop of ["DZ_TS_SITEKEY", "DZ_TS_SECRET", "DZ_GATE_SIGN"]) {
    const env = { ...ENV }; delete env[drop];
    const r = await get("/glossary/", { env });
    assert.equal(r.status, 200, drop); assert.equal(r.text, REAL);
  }
});

test("AIの取得役は、対象ページでは今までどおり冗談（関門より先）", async () => {
  const r = await get("/racers/racers_today.csv", { ua: "ChatGPT-User/1.0" });
  assert.equal(r.touched, false); assert.ok(r.text.includes("フリーザ"));
});

test("確認の受け口：確認に通れば印を出す・通らなければ403", async () => {
  const orig = globalThis.fetch;
  try {
    globalThis.fetch = async (url, init) => new Response(JSON.stringify({ success: String(init.body).includes("response=good") }));
    const ok = await get("/__gate/verify", { method: "POST", body: "t=good" });
    assert.equal(ok.status, 200);
    const m = /dzg=([^;]+)/.exec(ok.setCookie);
    assert.ok(m && await validPass("signkey", m[1]));
    assert.ok(ok.setCookie.includes("HttpOnly") && ok.setCookie.includes("Secure"));
    const ng = await get("/__gate/verify", { method: "POST", body: "t=bad" });
    assert.equal(ng.status, 403); assert.ok(!ng.setCookie.includes("dzg="));
  } finally { globalThis.fetch = orig; }
});

test("非常口：kv の gate:off が 1 なら関門を開ける。読めなければ関門は閉じたまま", async () => {
  const db = v => ({ prepare: () => ({ first: async () => (v === "err" ? (() => { throw new Error("x"); })() : (v ? { v } : null)) }) });
  assert.equal((await get("/glossary/", { env: { ...ENV, DZ_DB: db("1") } })).text, REAL);
  assert.equal((await get("/glossary/", { env: { ...ENV, DZ_DB: db("0") } })).status, 403);
  assert.equal((await get("/glossary/", { env: { ...ENV, DZ_DB: db(null) } })).status, 403);
  assert.equal((await get("/glossary/", { env: { ...ENV, DZ_DB: db("err") } })).status, 403);
});
