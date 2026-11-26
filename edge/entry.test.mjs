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

test("部品が HTML を渡したら、HTML のページの末尾にだけ足す。HTML 以外・200 以外・壊れた値では足さず、本物はそのまま", async () => {
  const mk = (tail) => ({ fetch: async () => new Response(null, { status: 204, headers: { "x-dz-pass": "1", "x-dz-tail": tail } }) });
  const go = async (guard, type, status = 200) => {
    const request = new Request("https://example.pages.dev/racers/", { headers: { "user-agent": "x" } });
    const res = await onRequest({ request, env: { DZ_GUARD: guard }, next: async () => new Response(status === 200 ? "<html><body><p>" + REAL + "</p></body></html>" : null, { status, headers: { "content-type": type } }) });
    return { status: res.status, text: await res.text() };
  };
  const orig = globalThis.HTMLRewriter;
  globalThis.HTMLRewriter = class { on(sel, h) { this.h = h; return this; } transform(res) { const h = this.h; return new Response(res.text().then(t => { let add = ""; h.element({ append(x) { add += x; } }); return t.replace("</body>", add + "</body>"); }).then(t => new Blob([t]).stream()).then(s => s), res); } };
  try {
    globalThis.HTMLRewriter = class { on(sel, h) { this.h = h; return this; } transform(res) { let add = ""; this.h.element({ append(x) { add += x; } }); const ts = new TransformStream(); (async () => { const t = await res.text(); const w = ts.writable.getWriter(); await w.write(new TextEncoder().encode(t.replace("</body>", add + "</body>"))); await w.close(); })(); return new Response(ts.readable, res); } };
    const a = await go(mk(encodeURIComponent("<i>x</i>")), "text/html; charset=utf-8");
    assert.ok(a.text.includes(REAL) && a.text.includes("<i>x</i></body>"));
    assert.ok(!(await go(mk(encodeURIComponent("<i>x</i>")), "application/json")).text.includes("<i>x</i>"));
    assert.equal((await go(mk(encodeURIComponent("<i>x</i>")), "text/html", 304)).status, 304);
    const bad = await go(mk("%E0%A4%A"), "text/html");
    assert.ok(bad.text.includes(REAL) && !bad.text.includes("%E0"));
    globalThis.HTMLRewriter = undefined;
    assert.ok((await go(mk(encodeURIComponent("<i>x</i>")), "text/html")).text.includes(REAL));
  } finally { globalThis.HTMLRewriter = orig; }
});
