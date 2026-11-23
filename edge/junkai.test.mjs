// node --test edge/junkai.test.mjs
// 連続巡回の記録が、罠と本物の返し方を一切変えないこと・記録の中身・失敗しても止まらないことを確かめる。
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../functions/_middleware.js";
import { FREEZA } from "./aiNotice.mjs";
import { visitorCookie, ipKey, jstDay, pathKind, recordVisit } from "./junkai.mjs";
const TRAP = JSON.stringify({ ai: ["testaiagent", "otheraibot", "zzfetch"], scr: ["test-scraper-a", "test-scraper-b"], asn: [64512], chk: "TestCheck/1.0", pre: "Q" });

const BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const REAL = "本物の中身 全国勝率 6.12";

function logEnv() {
  const points = [];
  return { points, env: { DZ_SALT: "testsalt", DZ_LOG: { writeDataPoint: p => points.push(p) } } };
}

async function get(path, { ua = BROWSER, lang = "ja-JP,ja;q=0.9", cookie, env, ip = "203.0.113.7" } = {}) {
  let touched = false;
  const headers = { "user-agent": ua, "accept-language": lang, "cf-connecting-ip": ip };
  if (cookie) headers.cookie = cookie;
  const request = new Request("https://example.pages.dev" + path, { headers });
  const res = await onRequest({ request, env: { DZ_TRAP: TRAP, ...(env || {}) }, next: async () => { touched = true; return new Response(REAL, { status: 200 }); } });
  return { status: res.status, text: await res.text(), touched, setCookie: res.headers.get("set-cookie") || "" };
}

test("記録あり：人間には本物、AIには冗談（罠は変わらない）", async () => {
  const { env, points } = logEnv();
  const h = await get("/racers/", { env });
  assert.equal(h.text, REAL); assert.equal(h.touched, true);
  const a = await get("/racers/", { env, ua: "TestAiAgent/1.0" });
  assert.equal(a.touched, false); assert.ok(a.text.includes(FREEZA));
  const t = await get("/", { env });
  assert.equal(t.text, REAL);
  assert.equal(points.length, 3);
  assert.equal(points[0].blobs[8], "real");
  assert.equal(points[1].blobs[8], "trap");
});

test("記録なし（バインディングが無い）でも、返す中身は同じで止まらない", async () => {
  const h = await get("/racers/");
  assert.equal(h.text, REAL);
  const a = await get("/racers/", { ua: "OtherAiBot/2.0" });
  assert.ok(a.text.includes(FREEZA));
  const bad = { DZ_SALT: "x", DZ_LOG: { writeDataPoint: () => { throw new Error("boom"); } } };
  const b = await get("/kensho/", { env: bad });
  assert.equal(b.text, REAL);
});

test("接続元は生のまま残さない・同じ日同じ接続元は同じ値・日が変われば別の値", async () => {
  const { env, points } = logEnv();
  await get("/", { env, ip: "203.0.113.7" });
  await get("/kensho/", { env, ip: "203.0.113.7" });
  await get("/", { env, ip: "198.51.100.9" });
  const [p1, p2, p3] = points;
  assert.match(p1.blobs[0], /^[0-9a-f]{16}$/);
  assert.equal(p1.blobs[0], p2.blobs[0]);
  assert.notEqual(p1.blobs[0], p3.blobs[0]);
  for (const p of points) assert.ok(!JSON.stringify(p).includes("203.0.113") && !JSON.stringify(p).includes("198.51.100"));
  const pts = [];
  const ctx = (d) => ({ request: new Request("https://example.pages.dev/", { headers: { "cf-connecting-ip": "203.0.113.7" } }), env: { DZ_SALT: "s", DZ_LOG: { writeDataPoint: p => pts.push(p) } } });
  await recordVisit(ctx(), { id: "0123456789abcdef", isNew: false }, false, Date.UTC(2026, 10, 9, 3));
  await recordVisit(ctx(), { id: "0123456789abcdef", isNew: false }, false, Date.UTC(2026, 10, 10, 3));
  assert.notEqual(pts[0].blobs[0], pts[1].blobs[0]);
});

test("Cookie：初回は dzv を配る、持って来た人には配り直さない", async () => {
  const { env, points } = logEnv();
  const a = await get("/", { env });
  assert.match(a.setCookie, /^dzv=[0-9a-f]{16}; Path=\/; Max-Age=31536000; SameSite=Lax; Secure; HttpOnly$/);
  assert.equal(points[0].blobs[2], "new");
  const id = a.setCookie.slice(4, 20);
  const b = await get("/kensho/", { env, cookie: `dzRaihou=x; dzv=${id}` });
  assert.equal(b.setCookie, "");
  assert.equal(points[1].blobs[1], id);
  assert.equal(points[1].blobs[2], "known");
  assert.equal(visitorCookie(new Request("https://e/", { headers: { cookie: "dzv=zz" } })).isNew, true);
});

test("小さな部品：IPv6は/64・JSTの日付・ページかデータか", () => {
  assert.equal(ipKey("2001:DB8:1:2:aaaa:bbbb:cccc:dddd"), "2001:db8:1:2::/64");
  assert.equal(ipKey("203.0.113.7"), "203.0.113.7");
  assert.equal(jstDay(Date.UTC(2026, 10, 9, 15, 30)), "2026-11-10");
  assert.equal(pathKind("/"), "page");
  assert.equal(pathKind("/kensho/buhin/"), "page");
  assert.equal(pathKind("/racers/index.html"), "page");
  assert.equal(pathKind("/players/card"), "page");
  assert.equal(pathKind("/racers/racers_today.csv"), "data");
  assert.equal(pathKind("/data/tenjiStats.json"), "data");
});

// 自動ブロック（edge/ban.mjs）。D1 は手元の作り物で代える
function fakeD1({ broken = false } = {}) {
  const hits = [], bans = new Map();
  const st = sql => ({
    bind: (...a) => ({
      first: async () => {
        if (broken) throw new Error("d1 down");
        if (sql.startsWith("SELECT k FROM junkaiBan")) { for (const k of [a[0], a[1]]) { const b = bans.get(k); if (b && b.until > a[2]) return { k }; } return null; }
        if (sql.startsWith("SELECT COUNT")) return { n: hits.filter(h => h.k === a[0] && h.t > a[1]).length };
        return null;
      },
      run: async () => {
        if (broken) throw new Error("d1 down");
        if (sql.startsWith("INSERT INTO junkaiHit")) hits.push({ k: a[0], t: a[1] });
        else if (sql.startsWith("INSERT OR REPLACE INTO junkaiBan")) bans.set(a[0], { kind: a[1], until: a[2], ua: a[3], asn: a[4] });
        else if (sql.startsWith("DELETE FROM junkaiHit")) for (let i = hits.length - 1; i >= 0; i--) if (hits[i].t < a[0]) hits.splice(i, 1);
        return {};
      },
    }),
  });
  return { hits, bans, prepare: st };
}

async function getB(path, env, { ua = "Mozilla/5.0 (compatible; somebot/1.0)", ip = "198.51.100.9", cookie, asn = 8075 } = {}) {
  let touched = false;
  const headers = { "user-agent": ua, "accept-language": "ja-JP,ja;q=0.9", "cf-connecting-ip": ip };
  if (cookie) headers.cookie = cookie;
  const request = new Request("https://example.pages.dev" + path, { headers });
  Object.defineProperty(request, "cf", { value: { asn } });
  const res = await onRequest({ request, env: { DZ_TRAP: TRAP, ...(env || {}) }, next: async () => { touched = true; return new Response(REAL, { status: 200 }); } });
  return { status: res.status, text: await res.text(), touched };
}

const PAGES = ["/", "/glossary/", "/kensho/players/", "/results/", "/stadium/"];

test("自動ブロック：Cookie を持ち帰らずに続けて開くと、しきい値で403。翌日も名乗りと回線で403", async () => {
  const db = fakeD1();
  const env = { DZ_SALT: "s", DZ_DB: db, DZ_BAN: "5,300,30" };
  for (let i = 0; i < 4; i++) assert.equal((await getB(PAGES[i % 5], env)).status, 200);
  const r = await getB("/stadium/", env);
  assert.equal(r.status, 403); assert.equal(r.touched, false); assert.ok(!r.text.includes(REAL));
  assert.equal((await getB("/data/weather.json", env)).status, 403);           // 同じ接続元はデータも拒否
  assert.equal((await getB("/", env, { ip: "198.51.100.77" })).status, 403);  // 接続元を変えても名乗りと回線で拒否
  assert.equal((await getB("/", env, { asn: 2516, ip: "198.51.100.78" })).status, 200);             // 別の回線なら同じ名乗りでも通る（接続元も別）
  assert.equal([...db.bans.values()].filter(b => b.kind === "fp").length, 1);
});

test("自動ブロック：Cookie を持ち帰る人は、速く開いても止めない", async () => {
  const db = fakeD1();
  const env = { DZ_SALT: "s", DZ_DB: db, DZ_BAN: "5,300,30" };
  for (let i = 0; i < 20; i++) {
    const r = await getB(PAGES[i % 5], env, { ua: BROWSER, cookie: "dzv=0123456789abcdef", asn: 2516 });
    assert.equal(r.status, 200); assert.equal(r.text, REAL);
  }
  assert.equal(db.bans.size, 0);
});

test("自動ブロック：配信WFの確認アクセスは名乗りと回線の組み合わせでは止めない", async () => {
  const db = fakeD1();
  const env = { DZ_SALT: "s", DZ_DB: db, DZ_BAN: "3,300,30" };
  const ua = "TestCheck/1.0";
  for (let i = 0; i < 3; i++) await getB(PAGES[i], env, { ua });
  assert.equal([...db.bans.values()].filter(b => b.kind === "fp").length, 0);
  assert.equal((await getB("/", env, { ua, ip: "198.51.100.200" })).status, 200);
});

test("自動ブロック：設定が無い・D1 が壊れているときは本物を返す（止めない）", async () => {
  for (const env of [{ DZ_SALT: "s", DZ_DB: fakeD1() }, { DZ_SALT: "s", DZ_DB: fakeD1({ broken: true }), DZ_BAN: "2,300,30" }, { DZ_SALT: "s", DZ_BAN: "2,300,30" }]) {
    for (let i = 0; i < 6; i++) {
      const r = await getB(PAGES[i % 5], env);
      assert.equal(r.status, 200); assert.equal(r.text, REAL);
    }
  }
});

test("自動ブロック：拒否は記録に block と残る", async () => {
  const db = fakeD1(); const points = [];
  const env = { DZ_SALT: "s", DZ_DB: db, DZ_BAN: "2,300,30", DZ_LOG: { writeDataPoint: p => points.push(p) } };
  await getB("/", env); await getB("/glossary/", env);
  assert.equal(points.at(-1).blobs[8], "block");
  assert.equal(points[0].blobs[8], "real");
});
