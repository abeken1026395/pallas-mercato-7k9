// 動かし方：node --test edge/live.test.mjs（Node 22 以上・配信WFの試験には入れていない）
// 今見ている人数・通知の受け口・送り役の試験。D1 の代わりに node:sqlite を同じ呼び方で包んで使う
import test from "node:test";
import assert from "node:assert";
import { DatabaseSync } from "node:sqlite";
import { onNow, onPush, cleanRaces, cleanFols, okEndpoint, SCHEMA } from "./live.mjs";
import { runOnce, msg10, msgRes, parseOfficial, findResult, toMs, followRaces } from "./pushWorker.mjs";

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

test("通知：レースの検査（形・日付の一致・期間・種類・重複・上限）", () => {
  const dl = T0 + 30 * 60000;
  const ok = cleanRaces([{ rid: "12_20261113_5", dl, m: 1 }, { rid: "12_20261113_5", dl, m: 1 }, { rid: "25_20261113_5", dl, m: 1 }, { rid: "12_20261114_5", dl, m: 1 }, { rid: "12_20261113_13", dl, m: 1 }, { rid: "<x>", dl, m: 1 }, { rid: "12_20261113_7", dl }, null, "x"], T0);
  assert.deepStrictEqual(ok, [{ rid: "12_20261113_5", dl, m: 1, k: 0 }]);
  // 締切を過ぎたレースは結果だけ受け付ける（3時間まで）
  assert.deepStrictEqual(cleanRaces([{ rid: "12_20261113_6", dl: T0 - 120000, m: 1, k: 1 }, { rid: "12_20261113_8", dl: T0 - 120000, m: 1 }, { rid: "12_20261113_1", dl: T0 - 4 * 3600000, k: 1 }], T0), [{ rid: "12_20261113_6", dl: T0 - 120000, m: 0, k: 1 }]);
  assert.strictEqual(cleanRaces("x", T0), null);
  const many = Array.from({ length: 150 }, (_, i) => ({ rid: "12_20261113_" + (i % 12 + 1), dl: dl + i, m: 1 }));
  assert.ok(cleanRaces(many, T0).length <= 12);
});

test("通知：登録・同じ内容は書かない・種類だけ直す・解除", async () => {
  const env = { DZ_DB: fakeD1() };
  const races = [{ rid: "12_20261113_5", dl: T0 + 20 * 60000, m: 1, k: 0 }];
  let r = await (await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races }), env }, T0)).json();
  assert.deepStrictEqual(r, { ok: true, n: 1, f: 0 });
  r = await (await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races }), env }, T0)).json();
  assert.strictEqual(r.same, true);
  env.DZ_DB.raw.prepare("UPDATE races SET dl = dl + 600000").run(); // 送り役が公式の時刻で直した
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [{ ...races[0], k: 1 }] }), env }, T0);
  const row = env.DZ_DB.raw.prepare("SELECT dl, m, k FROM races").get();
  assert.deepStrictEqual([row.dl, row.m, row.k], [T0 + 30 * 60000, 1, 1]);
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [] }), env }, T0);
  assert.strictEqual(env.DZ_DB.raw.prepare("SELECT COUNT(*) n FROM races").get().n, 0);
  await onPush({ request: req("/api/push", { a: "off", sub: SUB }), env }, T0);
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

const OFFI = (times) => times.map((t, i) => `<td class="is-fs14 is-fBold"><a href="/owpc/pc/race/racelist?rno=${i + 1}&amp;jcd=12&amp;hd=20261113">${i + 1}R</a>\n   </td>\n   <td>${t}</td>`).join("\n");
const RES = (j, rn, fin, pay) => `{"開催日":"20261113","場":[{"場コード":"${j}","レース":[{"場コード":"${j}","レース":"${rn}R","着順":"${fin}","1着":1,"三連単配当":${pay},"決まり手":"逃げ"}]}]}`;

test("送り役：公式の一覧の読み取り・結果の探し方・時刻", () => {
  assert.deepStrictEqual(parseOfficial(OFFI(["10:45", "11:12"])), { 1: "10:45", 2: "11:12" });
  assert.deepStrictEqual(findResult(RES("12", 5, "1-2-3", 1230), "12", "5"), { fin: "1-2-3", pay: 1230 });
  assert.strictEqual(findResult(RES("12", 5, "1-2-3", 1230), "12", "6"), null);
  assert.strictEqual(toMs("20261113", "15:10"), T0 + 10 * 60000);
});

test("送り役：10分前に1通・同じ分はまとめる・上限なし・締切後は送らない・消えた購読は消す", async () => {
  const env = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "https://site.test/" };
  const sent = [];
  const send = async (sub, payload) => { sent.push(JSON.parse(payload)); return 201; };
  const nofetch = async () => ({ ok: false });
  const at = (m) => T0 + m * 60000;
  const races = [1, 2, 3, 4, 5].map(i => ({ rid: "12_20261113_" + i, dl: at(10 + (i - 1) * 30), m: 1 }));
  races.push({ rid: "06_20261113_7", dl: at(10), m: 1 });
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races }), env }, T0 - 60000);
  let r = await runOnce(env, T0, send, nofetch);
  assert.strictEqual(r.sent, 1);
  assert.strictEqual(sent[0].t, "締切10分前｜浜名湖 7R");
  assert.strictEqual(sent[0].b, "15:10締切（ほか1レース）");
  assert.strictEqual(sent[0].u, "/racers/#v06r7d20261113");
  r = await runOnce(env, T0 + 60000, send, nofetch);
  assert.strictEqual(r.sent, 0);
  for (const m of [30, 60, 90, 120]) await runOnce(env, at(m), send, nofetch);
  assert.strictEqual(sent.length, 5); // 上限なし
  // 締切を過ぎたレースは送らない
  const env2 = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "https://site.test/" };
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [{ rid: "12_20261113_1", dl: at(10), m: 1 }] }), env: env2 }, T0 - 60000);
  r = await runOnce(env2, at(10), send, nofetch);
  assert.strictEqual(r.sent, 0);
  // 404・410 の購読は消す
  const env3 = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "https://site.test/" };
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [{ rid: "12_20261113_1", dl: at(10), m: 1 }] }), env: env3 }, T0 - 60000);
  r = await runOnce(env3, T0, async () => 410, nofetch);
  assert.strictEqual(r.gone, 1);
  assert.strictEqual(env3.DZ_DB.raw.prepare("SELECT COUNT(*) n FROM subs").get().n, 0);
});

test("送り役：締切が遅れたら公式の新しい時刻の10分前に送る", async () => {
  const env = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "https://site.test/" };
  const sent = [], urls = [];
  const send = async (sub, payload) => { sent.push(JSON.parse(payload)); return 201; };
  const times = ["10:45", "11:12", "11:39", "12:06", "15:20"]; // 5R は 15:10 → 15:20 に遅れた
  const f = async (u) => { urls.push(u); return { ok: true, text: async () => OFFI(times) }; };
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [{ rid: "12_20261113_5", dl: T0 + 10 * 60000, m: 1 }] }), env }, T0 - 60000);
  let r = await runOnce(env, T0, send, f);
  assert.strictEqual(r.sent, 0);
  assert.strictEqual(urls.length, 1);
  assert.match(urls[0], /raceindex\?jcd=12&hd=20261113$/);
  assert.strictEqual(env.DZ_DB.raw.prepare("SELECT dl FROM races").get().dl, T0 + 20 * 60000);
  r = await runOnce(env, T0 + 60000, send, f);
  assert.strictEqual(urls.length, 1); // 3分おき
  r = await runOnce(env, T0 + 10 * 60000, send, f);
  assert.strictEqual(r.sent, 1);
  assert.strictEqual(sent[0].t, "締切10分前｜住之江 5R");
  assert.strictEqual(sent[0].b, "15:20締切");
});

test("送り役：結果が入ったら送る・入らなければ3時間であきらめる", async () => {
  const env = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "https://site.test/" };
  const sent = [], urls = [];
  const send = async (sub, payload) => { sent.push(JSON.parse(payload)); return 201; };
  let body = '{"開催日":"20261113","場":[]}';
  const f = async (u) => { urls.push(u); return { ok: true, text: async () => body }; };
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [{ rid: "12_20261113_5", dl: T0, k: 1 }, { rid: "12_20261113_6", dl: T0, k: 1 }] }), env }, T0 - 60000);
  let r = await runOnce(env, T0 + 5 * 60000, send, f);
  assert.strictEqual(urls.length, 0); // 締切から10分たつまで読まない
  r = await runOnce(env, T0 + 12 * 60000, send, f);
  assert.strictEqual(urls[0], "https://site.test/results/data/20261113.json?_=" + (T0 + 12 * 60000));
  assert.strictEqual(r.sent, 0);
  body = RES("12", 5, "3-1-4", 12340);
  r = await runOnce(env, T0 + 13 * 60000, send, f);
  assert.strictEqual(urls.length, 1); // 2分おき
  r = await runOnce(env, T0 + 14 * 60000, send, f);
  assert.strictEqual(r.sent, 1);
  assert.deepStrictEqual(sent[0], { t: "結果｜住之江 5R", b: "3-1-4　3連単 12,340円", u: "/racers/#v12r5d20261113", g: "dz-r-12_20261113_5" });
  r = await runOnce(env, T0 + 3 * 3600000 + 60000, send, f);
  assert.strictEqual(env.DZ_DB.raw.prepare("SELECT COUNT(*) n FROM races WHERE sr = 0").get().n, 0);
  assert.strictEqual(sent.length, 1);
});

test("送り役：文面", () => {
  assert.deepStrictEqual(msg10([{ rid: "24_20261113_12", dl: Date.UTC(2026, 10, 13, 11, 40) }], Date.UTC(2026, 10, 13, 11, 31)), { t: "締切9分前｜大村 12R", b: "20:40締切", u: "/racers/#v24r12d20261113", g: "dz-24_20261113_12" });
  assert.deepStrictEqual(msgRes([{ rid: "24_20261113_12", fin: "1-2-3", pay: null }, { rid: "24_20261113_11", fin: "2-1-3", pay: 900 }]), { t: "結果｜大村 12R", b: "1-2-3（ほか1レース）", u: "/racers/#v24r12d20261113", g: "dz-r-24_20261113_12" });
});

// ---- 推し・モーターの出走（2026-11-17） ----
const ENT = (o) => JSON.stringify({ updated: "x", days: { "20261113": o } });
const E1 = { "12_5": ["15:20", ["4320", "3100", "4500", "4600", "4700", "4800"], ["34", "1", "2", "3", "4", "5"], ["島村隆幸", "A", "B", "C", "D", "E"]],
             "12_6": ["15:47", ["4100", "4320", "4500", "4600", "4700", "4800"], ["9", "8", "7", "6", "5", "4"], ["F", "島村隆幸", "B", "C", "D", "E"]],
             "02_3": ["15:25", ["1111", "2222", "3333", "4444", "5555", "6666"], ["34", "11", "12", "13", "14", "15"], ["G", "H", "I", "J", "K", "L"]] };

test("推し・モーター：一覧の検査", () => {
  assert.deepStrictEqual(cleanFols(["p:4320", "p:4320", "m:12_34", "m:25_1", "m:12_0", "p:43", "<x>", 5, "m:12_1000"]), ["m:12_34", "p:4320"]);
  assert.deepStrictEqual(cleanFols(undefined), []);
  assert.strictEqual(cleanFols("x"), null);
  assert.strictEqual(cleanFols(Array.from({ length: 80 }, (_, i) => "p:" + (1000 + i))).length, 40);
});

test("推し・モーター：締切40分前から足し、10分前に送る。文面に推し・モーター。同じレースは1回", async () => {
  const env = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "https://site.test/" };
  const sent = [], urls = [];
  const send = async (sub, payload) => { sent.push(JSON.parse(payload)); return 201; };
  const f = async (u) => { urls.push(u); if (/entryIndex/.test(u)) return { ok: true, text: async () => ENT(E1) }; return { ok: false }; };
  let r = await (await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: [], f: ["p:4320", "m:12_34", "m:02_34"] }), env }, T0 - 60000)).json();
  assert.deepStrictEqual(r, { ok: true, n: 0, f: 3 });
  r = await runOnce(env, T0 - 15 * 60000, send, f); // 14:45：15:20 と 15:25 は40分以内なので足す。15:47 はまだ
  assert.strictEqual(r.ent, 1);
  assert.match(urls[0], /^https:\/\/site\.test\/racers\/entryIndex\.json\?_=/);
  const rows = env.DZ_DB.raw.prepare("SELECT rid, o, m, k FROM races ORDER BY rid").all().map(x => [x.rid, x.o, x.m, x.k]);
  assert.deepStrictEqual(rows, [["02_20261113_3", "モーター 戸田34号機", 1, 0], ["12_20261113_5", "推し 島村隆幸", 1, 0]]);
  r = await runOnce(env, T0 - 14 * 60000, send, f);
  assert.strictEqual(r.ent, 0); // 10分おき
  r = await runOnce(env, T0 + 10 * 60000, send, f); // 15:10
  assert.strictEqual(r.sent, 1);
  assert.deepStrictEqual(sent[0], { t: "締切10分前｜住之江 5R", b: "15:20締切・推し 島村隆幸", u: "/racers/#v12r5d20261113", g: "dz-12_20261113_5" });
  await runOnce(env, T0 + 11 * 60000, send, f);
  r = await runOnce(env, T0 + 15 * 60000, send, f);
  assert.strictEqual(sent.length, 2);
  assert.strictEqual(sent[1].b, "15:25締切・モーター 戸田34号機");
  for (let m = 16; m <= 40; m++) await runOnce(env, T0 + m * 60000, send, f);
  assert.strictEqual(sent.length, 3);
  assert.strictEqual(sent[2].t, "締切10分前｜住之江 6R");
  for (let m = 41; m <= 50; m++) await runOnce(env, T0 + m * 60000, send, f);
  assert.strictEqual(sent.length, 3); // 同じレースは1回
});

test("推し・モーター：外したら送らない・本人が選んだレースは消さない・通知を止めたら消す", async () => {
  const env = { DZ_DB: fakeD1(), VAPID_PRIVATE: "{}", VAPID_SUB: "https://site.test/" };
  const sent = [];
  const send = async (sub, payload) => { sent.push(JSON.parse(payload)); return 201; };
  const f = async (u) => ({ ok: true, text: async () => ENT(E1) });
  const mine = [{ rid: "12_20261113_5", dl: T0 + 20 * 60000, k: 1 }];
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: mine, f: ["p:4320"] }), env }, T0 - 60000);
  await runOnce(env, T0 - 20 * 60000, send, f);
  let row = env.DZ_DB.raw.prepare("SELECT o, m, k FROM races WHERE rid = '12_20261113_5'").get();
  assert.deepStrictEqual([row.o, row.m, row.k], ["推し 島村隆幸", 1, 1]);
  // 推しを外す：本人が選んだ「結果」は残り、10分前と印は外れる
  await onPush({ request: req("/api/push", { a: "sync", sub: SUB, races: mine, f: [] }), env }, T0 - 15 * 60000);
  row = env.DZ_DB.raw.prepare("SELECT o, m, k FROM races WHERE rid = '12_20261113_5'").get();
  assert.deepStrictEqual([row.o, row.m, row.k], [null, 0, 1]);
  for (let m = -14; m <= 12; m++) await runOnce(env, T0 + m * 60000, send, f);
  assert.strictEqual(sent.length, 0);
  // 止めたら推しの一覧も消す
  await onPush({ request: req("/api/push", { a: "off", sub: SUB }), env }, T0);
  assert.strictEqual(env.DZ_DB.raw.prepare("SELECT COUNT(*) n FROM fols").get().n, 0);
});

test("推し・モーター：壊れた索引でも止まらない", () => {
  const fols = [{ sid: "a", k: "p:4320" }];
  assert.deepStrictEqual(followRaces(null, fols, T0), []);
  assert.deepStrictEqual(followRaces({ days: { "x": {}, "20261113": { "<x>": ["15:20"], "12_5": "x", "12_6": ["25:99", [], [], []] } } }, fols, T0), []);
  assert.deepStrictEqual(followRaces({ days: { "20261113": { "12_5": ["15:20", ["4320"], null, ["<b>島 村</b>"]] } } }, fols, T0).map(x => x.o), ["推し <b>島村</b>"]);
});
