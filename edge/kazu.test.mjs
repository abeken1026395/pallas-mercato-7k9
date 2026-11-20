// 動かし方：node --test edge/kazu.test.mjs（Node 22 以上・配信WFの試験には入れていない）
// 測るもの（回数だけ）の受け口の試験。D1 の代わりに node:sqlite を同じ呼び方で包んで使う
import test from "node:test";
import assert from "node:assert";
import { DatabaseSync } from "node:sqlite";
import { onKazu, SCHEMA_KAZU, KINDS } from "./kazu.mjs";

function fakeD1(broken = false) {
  const db = new DatabaseSync(":memory:");
  if (!broken) db.exec(SCHEMA_KAZU);
  const prep = (sql) => {
    const st = { args: [], bind(...a) { st.args = a; return st; },
      run: async () => { db.prepare(sql).run(...st.args); return {}; } };
    return st;
  };
  return { raw: db, prepare: prep };
}
const ORIGIN = "https://example.test";
function req(body, origin = ORIGIN, method = "POST") {
  const h = { "content-type": "text/plain", "cf-connecting-ip": "203.0.113.9" };
  if (origin) h.origin = origin;
  return new Request(ORIGIN + "/api/kazu", { method, headers: h, body: method === "POST" ? body : undefined });
}
const T0 = Date.UTC(2026, 10, 20, 6, 0); // 15:00 JST

test("種類ごとに日本時間の日付で回数を足す・何も残さない", async () => {
  const env = { DZ_DB: fakeD1() };
  for (const k of KINDS) {
    const r = await onKazu({ request: req(JSON.stringify({ k })), env }, T0);
    assert.strictEqual(r.status, 200);
  }
  await onKazu({ request: req('{"k":"save"}'), env }, T0);
  await onKazu({ request: req('{"k":"save"}'), env }, Date.UTC(2026, 10, 20, 15, 30)); // 翌日 00:30 JST
  const rows = env.DZ_DB.raw.prepare("SELECT day, k, n FROM kazu ORDER BY day, k").all().map(x => ({ ...x }));
  assert.deepStrictEqual(rows.filter(x => x.k === "save"), [{ day: "2026-11-20", k: "save", n: 2 }, { day: "2026-11-21", k: "save", n: 1 }]);
  assert.strictEqual(rows.length, KINDS.length + 1);
  const cols = env.DZ_DB.raw.prepare("SELECT name FROM pragma_table_info('kazu')").all().map(x => x.name);
  assert.deepStrictEqual(cols, ["day", "k", "n"]);
});

test("知らない種類・壊れた中身・よその呼び出し・POST以外は数えない", async () => {
  const env = { DZ_DB: fakeD1() };
  const bad = [req('{"k":"x"}'), req("{{{"), req('{"k":["save"]}'), req("x".repeat(5000)), req('{"k":"save"}', "https://evil.test"), req('{"k":"save"}', null), req(null, ORIGIN, "GET")];
  const st = [];
  for (const r of bad) st.push((await onKazu({ request: r, env }, T0)).status);
  assert.deepStrictEqual(st, [400, 400, 400, 400, 403, 403, 405]);
  assert.strictEqual(env.DZ_DB.raw.prepare("SELECT COUNT(*) c FROM kazu").get().c, 0);
});

test("表が無い・DBが無いときもページは止めない", async () => {
  assert.strictEqual((await onKazu({ request: req('{"k":"save"}'), env: { DZ_DB: fakeD1(true) } }, T0)).status, 503);
  assert.strictEqual((await onKazu({ request: req('{"k":"save"}'), env: {} }, T0)).status, 200);
});
