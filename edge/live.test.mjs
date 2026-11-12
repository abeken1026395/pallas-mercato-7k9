// 動かし方：node --test edge/live.test.mjs（Node 22 以上・配信WFの試験には入れていない）
// 今見ている人数・通知の受け口・送り役の試験。D1 の代わりに node:sqlite を同じ呼び方で包んで使う
import test from "node:test";
import assert from "node:assert";
import { DatabaseSync } from "node:sqlite";
import { onNow, onPush, cleanRaces, okEndpoint, SCHEMA } from "./live.mjs";
import { runOnce, message } from "./pushWorker.mjs";

function fakeD1() {
  const db = new DatabaseSync(":memory:");
  for (const s of SCHEMA) db.exec(s);
  const prep = (sql) => {
    const st = { args: [], bind(...a) { st.args = a; return st; },
      all: async () => ({ results: db.prepare(sql).all(...st.args) }),
      first: async () => db.prepare(sql).get(...st.args) ?? null,
      run: async () => { db.prepare(sql).run(...st.args); return {}; },
      _exec() { const p = db.prepare(sql); return /^\s*select/i.test(sql) ? { results: p.all(...st.args) } : (p.run(...st.args), { results: [] }); } };
    return st;
  };
  return { raw: db, prepare: prep, batch: async (sts) => { db.exec("BEGIN"); try { const r = sts.map(s => s._exec()); db.exec("COMMIT"); return r; } catch (e) { db.exec("ROLLBACK"); throw e; } } };
}
const ORIGIN = "https://example.test";
function req(path, body, ip = "203.0.113.5", origin = ORIGIN, method = "POST") {
  const h = { "cf-connecting-ip": ip, "content-type": "text/plain" };
  if (origin) h.origin = origin;
  return new Request(ORIGIN + path, { method, headers: h, body: method === "POST" ? (typeof body === "string" ? body : JSON.stringify(body)) : undefined });
}
const T0 = Date.UTC(2026, 10, 13, 6, 0); // 15:00 JST
const SUB = { endpoint: "https://web.push.apple.com/QAbc-123", keys: { p256dh: "B" + "A".repeat(86), auth: "A".repeat(22) } };

test("人数：5人未満は0、5人以上は実数。同じ接続元は1人", async () => {
  const env = { DZ_DB: fakeD1(), DZ_SALT: "s" };
  for (let i = 1; i <= 4; i++) {
    const r = await (await onNow({ request: req("/api/now", "1", "203.0.113." + i), env }, T0)).json();
    assert.strictEqual(r.n, 0);
  }
  await onNow({ request: req("/api/now", "1", "203.0.113.4"), env }, T0 + 1000);
  let r = await (await onNow({ request: req("/api/now", "1", "203.0.113.5"), env }, T0 + 2000)).json();
  assert.strictEqual(r.n, 5);
  // 5分たった人は数えない
  r = await (await onNow({ request: req("/api/now", "1", "203.0.113.6"), env }, T0 + 5 * 60000 + 1500)).json();
  assert.strictEqual(r.n, 0);
  // 生の接続元は保存しない
  const rows = env.DZ_DB.raw.prepare("SELECT k FROM ima").all();
  assert.ok(rows.every(x => /^[0-9a-f]{16}$/.test(x.k)));
});

test("人数：よそのサイト・GET・設定なしは断るか0", async () => {
  const env = { DZ_DB: fakeD1(), DZ_SALT: "s" };
  assert.strictEqual((await onNow({ request: req("/api/now", "1", "1.1.1.1", "https://evil.test"), env }, T0)).status, 403);
  assert.strictEqual((await onNow({ request: req("/api/now", "1", "1.1.1.1", null), env }, T0)).status, 403);
  assert.strictEqual((await onNow({ request: req("/api/now", null, "1.1.1.1", ORIGIN, "GET"), env }, T0)).status, 405);
  assert.deepStrictEqual(await (await onNow({ request: req("/api/now", "1"), env: {} }, T0)).json(), { n: 0 });
});

test("通知：送り先の検査", () => {
  assert.ok(okEndpoint("https://fcm.googleapis.com/fcm/send/x"));
  assert.ok(okEndpoint("https://web.push.apple.com/x"));
  assert.ok(!okEndpoint("http://web.push.apple.com/x"));
  assert.ok(!okEndpoint("https://evil.test/x"));
  assert.ok(!okEndpoint("https://web.push.apple.com.evil.test/x"));
  assert.ok(!okEndpoint(42));
});

test("通知：レースの検査（形・日付の一致・3日以内・重複・上限）", () => {
  const dl = T0 + 30 * 60000;
  const ok = cleanRaces([{ rid: "12_20261113_5", dl }, { rid: "12_20261113_5", dl }, { rid: "25_20261113_5", dl }, { rid: "12_20261114_5", dl }, { rid: "12_20261113_13", dl }, { rid: "<x>", dl }, { rid: "12_20261113_6", dl: T0 - 120000 }, null, "x"], T0);
  assert.deepStrictEqual(ok, [{ rid: "12_20261113_5", dl }]);
  assert.strictEqual(cleanRaces("x", T0), null);
  const many = Array.from({ length: 150 }, (_, i) => ({ rid: "12_20261113_" + (i % 12 + 1), dl: dl + i }));
  assert.ok(cleanRaces(many, T0).length <= 12);
});

test("通知：登録・同じ内容は書かない・解除", async () => {
  const env = { DZ_DB: fakeD1() };
  const races = [{ rid: "12_20261113_5", dl: T0 + 20 * 60000 }];
  let r = await (await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races }), env }, T0)).json();
  assert.deepStrictEqual(r, { ok: true, n: 1 });
  r = await (await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races }), env }, T0)).json();
  assert.strictEqual(r.same, true);
  r = await (await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [] }), env }, T0)).json();
  assert.strictEqual(env.DZ_DB.raw.prepare("SELECT COUNT(*) n FROM races").get().n, 0);
  r = await (await onPush({ request: req("/api/push", { a: "off", sub: SUB }), env }, T0)).json();
  assert.strictEqual(env.DZ_DB.raw.prepare("SELECT COUNT(*) n FROM subs").get().n, 0);
});

test("通知：壊れた本文・悪い送り先・よそのサイトは断る", async () => {
  const env = { DZ_DB: fakeD1() };
  assert.strictEqual((await onPush({ request: req("/api/push", "{"), env }, T0)).status, 400);
  assert.strictEqual((await onPush({ request: req("/api/push", { a: "sync", sub: { endpoint: "https://evil.test/", keys: SUB.keys }, races: [] }), env }, T0)).status, 400);
  assert.strictEqual((await onPush({ request: req("/api/push", { a: "sync", sub: { endpoint: SUB.endpoint, keys: { p256dh: "<script>", auth: "x" } }, races: [] }), env }, T0)).status, 400);
  assert.strictEqual((await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [] }, "1.1.1.1", "https://evil.test"), env }, T0)).status, 403);
  assert.strictEqual((await onPush({ request: req("/api/push", "x".repeat(30000)), env }, T0)).status, 413);
});

test("送り役：締切10分前に1通・同じ分のレースはまとめる・1日3通まで・締切後は送らない・消えた購読は消す", async () => {
  const env = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "mailto:x@example.test" };
  const sent = [];
  const send = async (sub, payload) => { sent.push(JSON.parse(payload)); return 201; };
  const at = (m) => T0 + m * 60000;
  const races = [1, 2, 3, 4, 5].map(i => ({ rid: "12_20261113_" + i, dl: at(10 + (i - 1) * 30) }));
  races.push({ rid: "06_20261113_7", dl: at(10) });
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races }), env }, T0 - 60000);
  let r = await runOnce(env, T0, send);
  assert.deepStrictEqual(r, { sent: 1, capped: 0, gone: 0, fail: 0 });
  assert.strictEqual(sent[0].t, "締切10分前｜浜名湖 7R");
  assert.match(sent[0].b, /^15:10締切。保存した買い目があります（ほか1レース）$/);
  assert.strictEqual(sent[0].u, "/racers/#v06r7d20261113");
  r = await runOnce(env, T0 + 60000, send);
  assert.strictEqual(r.sent, 0);
  for (const m of [30, 60, 90]) await runOnce(env, at(m), send);
  assert.strictEqual(sent.length, 3);
  // 締切を過ぎたレースは送らない
  const env2 = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "mailto:x@example.test" };
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [{ rid: "12_20261113_1", dl: at(10) }] }), env: env2 }, T0 - 60000);
  r = await runOnce(env2, at(10), send);
  assert.strictEqual(r.sent, 0);
  // 404 の購読は消す
  const env3 = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "mailto:x@example.test" };
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [{ rid: "12_20261113_1", dl: at(10) }] }), env: env3 }, T0 - 60000);
  r = await runOnce(env3, T0, async () => 410);
  assert.strictEqual(r.gone, 1);
  assert.strictEqual(env3.DZ_DB.raw.prepare("SELECT COUNT(*) n FROM subs").get().n, 0);
});

test("送り役：文面", () => {
  const m = message([{ rid: "24_20261113_12", dl: Date.UTC(2026, 10, 13, 11, 40) }], Date.UTC(2026, 10, 13, 11, 31));
  assert.deepStrictEqual(m, { t: "締切9分前｜大村 12R", b: "20:40締切。保存した買い目があります", u: "/racers/#v24r12d20261113", g: "dz-24_20261113_12" });
});
