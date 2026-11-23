// node --test edge/entry.test.mjs
// 入口：部品の答えが「通す」なら本物（部品の Cookie を写す）、それ以外は部品の答え。部品が無い・落ちているときは本物。
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../functions/_middleware.js";

const REAL = "本物";
async function run(path, guard, { method = "GET", body } = {}) {
  let touched = false;
  const init = { method, headers: { "user-agent": "x" } };
  if (body) init.body = body;
  const request = new Request("https://example.pages.dev" + path, init);
  Object.defineProperty(request, "cf", { value: { asn: 1, country: "JP", colo: "KIX" } });
  const env = guard === undefined ? {} : { DZ_GUARD: guard, DZ_SALT: "s" };
  const res = await onRequest({ request, env, next: async () => { touched = true; return new Response(REAL, { status: 200 }); } });
  return { status: res.status, text: await res.text(), touched, cookies: res.headers.getSetCookie() };
}

test("通す答え：本物を返し、部品の Cookie を写す。部品には設定と回線の情報が渡る", async () => {
  let seen;
  const g = { fetch: async req => { seen = req; const h = new Headers({ "x-dz-pass": "1" }); h.append("set-cookie", "a=1"); h.append("set-cookie", "b=2"); return new Response(null, { status: 204, headers: h }); } };
  const r = await run("/racers/", g);
  assert.equal(r.text, REAL); assert.equal(r.touched, true); assert.deepEqual(r.cookies, ["a=1", "b=2"]);
  assert.equal(JSON.parse(seen.headers.get("x-dz-env")).DZ_SALT, "s");
  assert.equal(JSON.parse(seen.headers.get("x-dz-cf")).country, "JP");
});

test("止める答え：部品の答えをそのまま返し、本物に触れない", async () => {
  const g = { fetch: async () => new Response("no", { status: 403 }) };
  const r = await run("/racers/", g);
  assert.equal(r.status, 403); assert.equal(r.text, "no"); assert.equal(r.touched, false);
});

test("POST の中身も部品に渡る", async () => {
  let got;
  const g = { fetch: async req => { got = await req.text(); return new Response("ok", { status: 200 }); } };
  const r = await run("/x", g, { method: "POST", body: "token=abc" });
  assert.equal(got, "token=abc"); assert.equal(r.text, "ok");
});

test("部品が無い・例外・500 のときは本物。/api/ は部品を通さない", async () => {
  assert.equal((await run("/racers/")).text, REAL);
  assert.equal((await run("/racers/", { fetch: async () => { throw new Error("x"); } })).text, REAL);
  assert.equal((await run("/racers/", { fetch: async () => new Response("e", { status: 500 }) })).text, REAL);
  let called = false;
  assert.equal((await run("/api/now", { fetch: async () => { called = true; return new Response("no", { status: 403 }); } })).text, REAL);
  assert.equal(called, false);
});
