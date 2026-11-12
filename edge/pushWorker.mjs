// プッシュ通知の送り役（Cloudflare Workers・1分ごとの定時起動）。再訪設計 段階3（2026-11-13）。
// 配置はリポジトリの配信WFではなく、Cloudflare の Workers に直接置く（名前 dz-push・定時 "* * * * *"）。この本文はその控え。
// 必要な設定：D1（バインディング名 DZ_DB・Pages と同じデータベース）、秘密の値 VAPID_PRIVATE（P-256 の秘密鍵 JWK）・VAPID_SUB（連絡先の https か mailto）。
// 送るもの：保存した買い目のあるレースの締切10分前。1人1日3通まで（日本時間）。同じ分に重なったレースは1通にまとめる。
// 締切を過ぎたレースには送らない。届かなかった購読（404・410）は消す。
import { sendPush } from "./webPush.mjs";
import { jstDay } from "./junkai.mjs";

export const LEAD_MS = 10 * 60 * 1000;
export const DAILY_MAX = 3;
const JO = { "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国", "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松", "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村" };

export function hhmm(ms) { return new Date(ms + 9 * 3600000).toISOString().slice(11, 16); }

// 1人分の知らせの中身。races は締切の早い順
export function message(races, now) {
  const r = races[0];
  const [j, hd, rn] = r.rid.split("_");
  const min = Math.max(1, Math.round((r.dl - now) / 60000));
  const more = races.length > 1 ? "ほか" + (races.length - 1) + "レース" : "";
  return {
    t: "締切" + min + "分前｜" + (JO[j] || j) + " " + rn + "R",
    b: hhmm(r.dl) + "締切。保存した買い目があります" + (more ? "（" + more + "）" : ""),
    u: "/racers/#v" + j + "r" + rn + "d" + hd,
    g: "dz-" + r.rid,
  };
}

export async function runOnce(env, now = Date.now(), send = sendPush) {
  const db = env.DZ_DB;
  if (!db || !env.VAPID_PRIVATE || !env.VAPID_SUB) return { skip: true };
  const jwk = typeof env.VAPID_PRIVATE === "string" ? JSON.parse(env.VAPID_PRIVATE) : env.VAPID_PRIVATE;
  const due = await db.prepare(
    "SELECT r.sid, r.rid, r.dl, s.ep, s.p256dh, s.auth FROM races r JOIN subs s ON s.id = r.sid WHERE r.sent = 0 AND r.dl > ?1 AND r.dl <= ?2 ORDER BY r.sid, r.dl, r.rid"
  ).bind(now + 30000, now + LEAD_MS + 30000).all();
  const by = new Map();
  for (const x of due.results || []) {
    if (!by.has(x.sid)) by.set(x.sid, { sub: { ep: x.ep, p256dh: x.p256dh, auth: x.auth }, races: [] });
    by.get(x.sid).races.push({ rid: x.rid, dl: x.dl });
  }
  const day = jstDay(now);
  const out = { sent: 0, capped: 0, gone: 0, fail: 0 };
  for (const [sid, g] of by) {
    const st = [];
    const used = await db.prepare("SELECT n FROM daily WHERE sid = ?1 AND day = ?2").bind(sid, day).first();
    const n = used ? Number(used.n) : 0;
    // 送れたかどうかにかかわらず、この回のレースは送り済みにする（同じレースに2通送らない）
    for (const r of g.races) st.push(db.prepare("UPDATE races SET sent = 1 WHERE sid = ?1 AND rid = ?2").bind(sid, r.rid));
    if (n >= DAILY_MAX) { out.capped++; await db.batch(st); continue; }
    let code = 0;
    try { code = await send(g.sub, JSON.stringify(message(g.races, now)), jwk, env.VAPID_SUB); } catch (e) { code = -1; }
    if (code === 404 || code === 410) {
      out.gone++;
      st.push(db.prepare("DELETE FROM races WHERE sid = ?1").bind(sid), db.prepare("DELETE FROM daily WHERE sid = ?1").bind(sid), db.prepare("DELETE FROM subs WHERE id = ?1").bind(sid));
    } else if (code >= 200 && code < 300) {
      out.sent++;
      st.push(db.prepare("INSERT INTO daily (sid, day, n) VALUES (?1, ?2, 1) ON CONFLICT(sid, day) DO UPDATE SET n = n + 1").bind(sid, day));
    } else {
      out.fail++;
    }
    await db.batch(st);
  }
  // 片づけ：締切から1日たったレース、2日前より古い日の数、30日使われていない購読
  if (new Date(now).getUTCMinutes() % 30 === 0) {
    await db.batch([
      db.prepare("DELETE FROM races WHERE dl < ?1").bind(now - 86400000),
      db.prepare("DELETE FROM daily WHERE day < ?1").bind(jstDay(now - 2 * 86400000)),
      db.prepare("DELETE FROM races WHERE sid IN (SELECT id FROM subs WHERE seen < ?1)").bind(now - 30 * 86400000),
      db.prepare("DELETE FROM subs WHERE seen < ?1").bind(now - 30 * 86400000),
    ]);
  }
  return out;
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runOnce(env, event.scheduledTime || Date.now()).then(r => console.log(JSON.stringify(r))).catch(e => console.log("失敗", String(e))));
  },
  async fetch() { return new Response("", { status: 404 }); },
};
