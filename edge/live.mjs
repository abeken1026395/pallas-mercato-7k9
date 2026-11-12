// 今見ている人数とプッシュ通知の受け口（再訪設計 段階3・2026-11-13 けん「全てプロ仕様で」）。
// 置き場所：Pages Functions（functions/api/now.js・functions/api/push.js）から呼ぶ。保存先は D1（バインディング名 DZ_DB）。
// 人数：接続元を日替わりの鍵（DZ_SALT）で変換した16桁を、直近5分に合図があった数だけ数える。生の接続元は残さない。5人未満は0と返す。
// 通知：通知をオンにした人の購読情報と、保存した買い目のレース番号・締切時刻だけを受け取る。金額・メモ・収支は受け取らない。
// D1 が無い・失敗したときは何もせず空の答えを返す（ページを止めない）。
import { ipKey, jstDay } from "./junkai.mjs";

export const WINDOW_MS = 5 * 60 * 1000;   // 直近5分
export const SHOW_MIN = 5;                // 5人以上のときだけ出す
export const MAX_RACES = 60;              // 1人が登録できるレースの上限
const RID = /^(0[1-9]|1\d|2[0-4])_(\d{8})_([1-9]|1[0-2])$/;
const PUSH_HOSTS = [/^fcm\.googleapis\.com$/, /^android\.googleapis\.com$/, /^updates\.push\.services\.mozilla\.com$/, /^push\.services\.mozilla\.com$/, /^([a-z0-9-]+\.)*push\.apple\.com$/, /^([a-z0-9-]+\.)*notify\.windows\.com$/];

export const SCHEMA = [
  "CREATE TABLE IF NOT EXISTS ima (k TEXT PRIMARY KEY, t INTEGER NOT NULL)",
  "CREATE INDEX IF NOT EXISTS ima_t ON ima(t)",
  "CREATE TABLE IF NOT EXISTS subs (id TEXT PRIMARY KEY, ep TEXT NOT NULL, p256dh TEXT NOT NULL, auth TEXT NOT NULL, h TEXT, created INTEGER NOT NULL, seen INTEGER NOT NULL)",
  "CREATE TABLE IF NOT EXISTS races (sid TEXT NOT NULL, rid TEXT NOT NULL, dl INTEGER NOT NULL, sent INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (sid, rid))",
  "CREATE INDEX IF NOT EXISTS races_due ON races(sent, dl)",
  "CREATE TABLE IF NOT EXISTS daily (sid TEXT NOT NULL, day TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (sid, day))",
];

function hex(buf) { return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, "0")).join(""); }
async function sha(s) { return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s))); }

export function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex" } });
}

// 同じサイトのページからの呼び出しだけ受ける（Origin が無い・違うものは断る）
export function sameOrigin(request) {
  const o = request.headers.get("origin");
  if (!o) return false;
  try { return new URL(o).host === new URL(request.url).host; } catch (e) { return false; }
}

export async function onNow(context, now = Date.now()) {
  const { request, env } = context;
  if (request.method !== "POST") return json({ n: 0 }, 405);
  if (!sameOrigin(request)) return json({ n: 0 }, 403);
  if (!env || !env.DZ_DB || !env.DZ_SALT) return json({ n: 0 });
  try {
    const ip = request.headers.get("cf-connecting-ip") || "";
    if (!ip) return json({ n: 0 });
    const k = (await sha(env.DZ_SALT + "|ima|" + jstDay(now) + "|" + ipKey(ip))).slice(0, 16);
    const db = env.DZ_DB;
    const st = [
      db.prepare("INSERT INTO ima (k, t) VALUES (?1, ?2) ON CONFLICT(k) DO UPDATE SET t = excluded.t").bind(k, now),
      db.prepare("SELECT COUNT(*) AS n FROM ima WHERE t > ?1").bind(now - WINDOW_MS),
    ];
    if (Math.random() < 0.05) st.push(db.prepare("DELETE FROM ima WHERE t < ?1").bind(now - 3 * WINDOW_MS));
    const r = await db.batch(st);
    const n = Number((r[1].results && r[1].results[0] && r[1].results[0].n) || 0);
    return json({ n: n >= SHOW_MIN ? n : 0 });
  } catch (e) {
    return json({ n: 0 });
  }
}

export function okEndpoint(ep) {
  if (typeof ep !== "string" || ep.length > 1000) return false;
  try {
    const u = new URL(ep);
    return u.protocol === "https:" && PUSH_HOSTS.some(re => re.test(u.hostname));
  } catch (e) { return false; }
}

// レース番号（場_日付_R）と締切（ミリ秒）。日付は締切の日本時間の日付と一致し、締切は今から3日以内
export function cleanRaces(list, now = Date.now()) {
  if (!Array.isArray(list)) return null;
  const out = new Map();
  for (const x of list.slice(0, 200)) {
    if (!x || typeof x !== "object") continue;
    const m = RID.exec(String(x.rid || ""));
    const dl = Number(x.dl);
    if (!m || !Number.isFinite(dl)) continue;
    if (dl < now - 60000 || dl > now + 3 * 86400000) continue;
    if (jstDay(dl).replace(/-/g, "") !== m[2]) continue;
    out.set(x.rid, Math.floor(dl));
  }
  return [...out.entries()].sort((a, b) => a[1] - b[1]).slice(0, MAX_RACES).map(([rid, dl]) => ({ rid, dl }));
}

export async function onPush(context, now = Date.now()) {
  const { request, env } = context;
  if (request.method !== "POST") return json({ ok: false }, 405);
  if (!sameOrigin(request)) return json({ ok: false }, 403);
  if (!env || !env.DZ_DB) return json({ ok: false, e: "off" }, 503);
  let body;
  try {
    const txt = await request.text();
    if (txt.length > 20000) return json({ ok: false }, 413);
    body = JSON.parse(txt);
  } catch (e) { return json({ ok: false }, 400); }
  if (!body || typeof body !== "object") return json({ ok: false }, 400);
  const sub = body.sub || {};
  const ep = sub.endpoint;
  if (!okEndpoint(ep)) return json({ ok: false }, 400);
  const id = (await sha("sub|" + ep)).slice(0, 32);
  const db = env.DZ_DB;
  try {
    if (body.a === "off") {
      await db.batch([
        db.prepare("DELETE FROM races WHERE sid = ?1").bind(id),
        db.prepare("DELETE FROM daily WHERE sid = ?1").bind(id),
        db.prepare("DELETE FROM subs WHERE id = ?1").bind(id),
      ]);
      return json({ ok: true });
    }
    if (body.a !== "sync") return json({ ok: false }, 400);
    const keys = sub.keys || {};
    if (typeof keys.p256dh !== "string" || typeof keys.auth !== "string" || !/^[A-Za-z0-9_-]{80,100}$/.test(keys.p256dh) || !/^[A-Za-z0-9_-]{16,32}$/.test(keys.auth)) return json({ ok: false }, 400);
    const races = cleanRaces(body.races, now);
    if (!races) return json({ ok: false }, 400);
    const h = (await sha(JSON.stringify(races) + "|" + keys.p256dh + "|" + keys.auth)).slice(0, 16);
    const cur = await db.prepare("SELECT h FROM subs WHERE id = ?1").bind(id).first();
    if (cur && cur.h === h) {
      await db.prepare("UPDATE subs SET seen = ?2 WHERE id = ?1").bind(id, now).run();
      return json({ ok: true, n: races.length, same: true });
    }
    const st = [
      db.prepare("INSERT INTO subs (id, ep, p256dh, auth, h, created, seen) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6) ON CONFLICT(id) DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth, h = excluded.h, seen = excluded.seen").bind(id, ep, keys.p256dh, keys.auth, h, now),
      // 送り済みの印は残したまま、今回の一覧に無いレースを消し、新しいレースを足す
      db.prepare("DELETE FROM races WHERE sid = ?1 AND rid NOT IN (SELECT value FROM json_each(?2))").bind(id, JSON.stringify(races.map(r => r.rid))),
    ];
    for (const r of races) st.push(db.prepare("INSERT INTO races (sid, rid, dl, sent) VALUES (?1, ?2, ?3, 0) ON CONFLICT(sid, rid) DO UPDATE SET dl = excluded.dl").bind(id, r.rid, r.dl));
    await db.batch(st);
    return json({ ok: true, n: races.length });
  } catch (e) {
    return json({ ok: false, e: "db" }, 500);
  }
}
