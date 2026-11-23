// node --test edge/gate.test.mjs
// 人間確認の関門：印が無ければページは確認画面・データは403、印があれば本物、合図があれば本物、鍵が無ければ関門は開いたまま。
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../functions/_middleware.js";
import { makePass, validPass, isOpenPath, bindOf, GATE_COOKIE } from "./gate.mjs";

const BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const REAL = "本物の中身 全国勝率 6.12";
const ENV = { DZ_TS_SITEKEY: "0xSITE", DZ_TS_SECRET: "sec", DZ_GATE_SIGN: "signkey", DZ_GATE_KEY: "gatekey" };

async function get(path, { env = ENV, ua = BROWSER, cookie, key, method = "GET", body, country, asn } = {}) {
  let touched = false;
  const headers = { "user-agent": ua, "accept-language": "ja-JP,ja;q=0.9", "cf-connecting-ip": "203.0.113.5" };
  if (cookie) headers.cookie = cookie;
  if (key) headers["x-dz-key"] = key;
  const init = { method, headers };
  if (body) { init.body = body; headers["content-type"] = "application/x-www-form-urlencoded"; }
  const request = new Request("https://example.pages.dev" + path, init);
  if (country || asn) Object.defineProperty(request, "cf", { value: { country, asn } });
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
  const pass = await makePass("signkey", Date.now(), await bindOf(BROWSER, 0));
  for (const p of [...PAGES, ...DATA]) {
    const r = await get(p, { cookie: `${GATE_COOKIE}=${pass}; dzv=0123456789abcdef` });
    assert.equal(r.status, 200, p); assert.equal(r.text, REAL);
  }
  const forged = pass.slice(0, -1) + (pass.endsWith("0") ? "1" : "0");
  assert.equal((await get("/", { cookie: `${GATE_COOKIE}=${forged}` })).status, 403);
  const old = await makePass("signkey", Date.now() - 40 * 86400000, await bindOf(BROWSER, 0));
  assert.equal(await validPass("signkey", old, Date.now(), await bindOf(BROWSER, 0)), "");
  assert.equal(await validPass("otherkey", pass, Date.now(), await bindOf(BROWSER, 0)), "");
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
    assert.ok(m && await validPass("signkey", m[1], Date.now(), await bindOf(BROWSER, 0)));
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

test("海外：日本以外はページもデータも403（印があっても）。国が分からない・日本なら今までどおり", async () => {
  const pass = await makePass("signkey", Date.now(), await bindOf(BROWSER, 0));
  for (const p of [...PAGES, ...DATA]) {
    const r = await get(p, { country: "US", cookie: `${GATE_COOKIE}=${pass}` });
    assert.equal(r.status, 403, p); assert.equal(r.touched, false, p); assert.ok(!r.text.includes(REAL));
  }
  assert.ok((await get("/glossary/", { country: "US" })).text.includes("日本国内からのみ"));
  assert.equal((await get("/glossary/", { country: "JP", cookie: `${GATE_COOKIE}=${pass}` })).text, REAL);
  assert.equal((await get("/glossary/", { cookie: `${GATE_COOKIE}=${pass}` })).text, REAL);
});

test("海外：関門の外・秘密の合図・AIの取得役への冗談・非常口", async () => {
  for (const p of ["/in/line/shogo/", "/kiyaku/", "/api/now", "/assets/guard.js"]) assert.equal((await get(p, { country: "US" })).text, REAL, p);
  assert.equal((await get("/racers/entryIndex.json", { country: "US", key: "gatekey" })).text, REAL);
  const ai = await get("/racers/racers_today.csv", { country: "US", ua: "ChatGPT-User/1.0" });
  assert.ok(ai.text.includes("フリーザ"));
  const db = { prepare: sql => ({ first: async () => (sql.includes("'geo:off'") ? { v: "1" } : null) }) };
  const r = await get("/glossary/", { country: "US", env: { ...ENV, DZ_DB: db } });
  assert.equal(r.status, 403); assert.ok(r.text.includes("cf-turnstile"));
});

test("海外：関門の鍵が無くても海外拒否は効く", async () => {
  assert.equal((await get("/glossary/", { country: "DE", env: {} })).status, 403);
  assert.equal((await get("/glossary/", { country: "JP", env: {} })).text, REAL);
});

test("印のひもづけ：別の名乗り・別の回線に写した印は使えない", async () => {
  const pass = await makePass("signkey", Date.now(), await bindOf(BROWSER, 2516));
  const ck = `${GATE_COOKIE}=${pass}`;
  assert.equal((await get("/glossary/", { cookie: ck, asn: 2516 })).text, REAL);
  assert.equal((await get("/glossary/", { cookie: ck, asn: 9605 })).status, 403);
  assert.equal((await get("/glossary/", { cookie: ck, asn: 2516, ua: "python-requests/2.32" })).status, 403);
  assert.equal((await get("/data/weather.json", { cookie: ck, asn: 9605 })).status, 403);
  const old = pass.split(".")[0] + "." + pass.split(".")[2];
  assert.equal((await get("/glossary/", { cookie: `${GATE_COOKIE}=${old}`, asn: 2516 })).status, 403);
});

function capDb({ broken = false } = {}) {
  const use = [], ban = new Map();
  return { use, ban, prepare: sql => ({ bind: (...a) => ({
    first: async () => {
      if (broken) throw new Error("d1 down");
      if (sql.startsWith("SELECT p FROM gateBan")) { const u = ban.get(a[0]); return u && u > a[1] ? { p: a[0] } : null; }
      if (sql.startsWith("SELECT COUNT")) return { n: use.filter(x => x.p === a[0] && x.t > a[1]).length };
      return null;
    },
    run: async () => {
      if (broken) throw new Error("d1 down");
      if (sql.startsWith("INSERT INTO gateUse")) use.push({ p: a[0], t: a[1] });
      else if (sql.startsWith("INSERT OR REPLACE INTO gateBan")) ban.set(a[0], a[1]);
      return {};
    },
  }), first: async () => null }) };
}

test("印ごとの量の上限：超えたらその印は無効（ページもデータも403）。上限内と、記録が壊れているときは本物", async () => {
  const pass = await makePass("signkey", Date.now(), await bindOf(BROWSER, 0));
  const ck = `${GATE_COOKIE}=${pass}`;
  const db = capDb();
  const env = { ...ENV, DZ_DB: db, DZ_GATE_CAP: "10,300" };
  for (let i = 0; i < 10; i++) assert.equal((await get(PAGES[i % PAGES.length], { cookie: ck, env })).text, REAL, String(i));
  assert.equal((await get("/data/weather.json", { cookie: ck, env })).text, REAL);
  const over = await get("/glossary/", { cookie: ck, env });
  assert.equal(over.status, 403); assert.ok(over.text.includes("cf-turnstile"));
  assert.equal((await get("/data/weather.json", { cookie: ck, env })).status, 403);
  const env2 = { ...ENV, DZ_DB: capDb({ broken: true }), DZ_GATE_CAP: "10,300" };
  for (let i = 0; i < 15; i++) assert.equal((await get("/glossary/", { cookie: ck, env: env2 })).text, REAL);
  for (let i = 0; i < 15; i++) assert.equal((await get("/glossary/", { cookie: ck, env: { ...ENV, DZ_DB: capDb() } })).text, REAL);
});

test("拒否した相手だけ接続元を記録する（普通の来訪者は記録しない・記録が壊れていても拒否は続く）", async () => {
  const rows = [];
  const logDb = (broken) => ({ prepare: sql => ({ bind: (...a) => ({
    run: async () => { if (broken) throw new Error("x"); if (sql.startsWith("INSERT INTO blockLog")) rows.push(a); return {}; },
    first: async () => null, all: async () => ({ results: [] }) }), first: async () => null }) });
  const env = { ...ENV, DZ_DB: logDb(false) };
  const r = await get("/glossary/", { env, ua: "Mozilla/5.0 (compatible; slit-radar-import/1.0)" });
  assert.equal(r.status, 403); assert.equal(r.touched, false);
  assert.equal(rows.length, 1); assert.equal(rows[0][1], "203.0.113.5"); assert.equal(rows[0][7], "ua");
  await get("/glossary/", { env });
  assert.equal(rows.length, 1);
  const r2 = await get("/glossary/", { env: { ...ENV, DZ_DB: logDb(true) }, ua: "Mozilla/5.0 (compatible; slit-radar-import/1.0)" });
  assert.equal(r2.status, 403);
});
