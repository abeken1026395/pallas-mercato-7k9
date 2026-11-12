// プッシュ通知の送り役（Cloudflare Workers・1分ごとの定時起動）。再訪設計 段階3（2026-11-13）。
// 配置はリポジトリの配信WFではなく、Cloudflare の Workers に直接置く（名前 dz-push・定時 "* * * * *"）。この本文はその控え。
// 必要な設定：D1（バインディング名 DZ_DB・Pages と同じデータベース）、秘密の値 VAPID_PRIVATE（P-256 の秘密鍵 JWK）・VAPID_SUB（連絡先の https）。
//   サイトの住所は VAPID_SUB の住所を使う（結果データを読むため）。住所はリポジトリに書かない。
// 送るもの（どちらも、出走表・見どころで本人が選んだレースだけ・1日の上限なし＝2026-11-13 けん裁定）：
//   10分前：締切の10分前。締切は公式の締切予定時刻（場ごとの一覧ページ）で確かめ、ずれたら新しい時刻の10分前に送る。
//           同じ分に重なったレースは1通にまとめる。締切を過ぎたら送らない。
//   結果：サイトの結果データ（/results/data/YYYYMMDD.json）に着順が入ったら送る。締切から3時間入らなければあきらめる。
// 届かなかった購読（404・410）は消す。
import { sendPush } from "./webPush.mjs";
import { jstDay } from "./junkai.mjs";

export const LEAD_MS = 10 * 60 * 1000;
const OFFI_EVERY = 3 * 60 * 1000;      // 公式の締切を読み直す間隔（場ごと）
const OFFI_MAX = 4;                     // 1回に読む場の数の上限
const RES_EVERY = 2 * 60 * 1000;        // 結果データを読み直す間隔（日ごと）
const RES_GIVEUP = 3 * 3600 * 1000;
const JO = { "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国", "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松", "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村" };

export function hhmm(ms) { return new Date(ms + 9 * 3600000).toISOString().slice(11, 16); }
function parts(rid) { const [j, hd, rn] = rid.split("_"); return { j, hd, rn }; }
function name(j) { return JO[j] || j; }

// 日付（YYYYMMDD）と「時:分」から締切のミリ秒（日本時間）
export function toMs(hd, t) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(t || "");
  if (!m || !/^\d{8}$/.test(hd)) return null;
  return Date.UTC(+hd.slice(0, 4), +hd.slice(4, 6) - 1, +hd.slice(6, 8), +m[1] - 9, +m[2]);
}

// 公式の場ごとの一覧ページから {R番号: "HH:MM"} を読む
export function parseOfficial(html) {
  const out = {};
  const re = /racelist\?rno=(\d{1,2})&amp;jcd=\d{2}&amp;hd=\d{8}">\d{1,2}R<\/a>\s*<\/td>\s*<td>(\d{1,2}:\d{2})<\/td>/g;
  let m;
  while ((m = re.exec(html))) out[+m[1]] = m[2];
  return out;
}

// サイトの結果データ（文字列のまま）から、そのレースの着順と3連単の配当を探す（全体を読み解かずに済ませる）
export function findResult(text, j, rn) {
  const key = '"場コード":"' + j + '","レース":"' + rn + 'R","着順":"';
  const i = text.indexOf(key);
  if (i < 0) return null;
  const s = i + key.length, e = text.indexOf('"', s);
  const fin = text.slice(s, e);
  if (!/^\d-\d-\d$/.test(fin)) return null;
  const pm = /"三連単配当":(\d+)/.exec(text.slice(e, e + 200));
  return { fin, pay: pm ? +pm[1] : null };
}

export function msg10(races, now) {
  const r = races[0], p = parts(r.rid);
  const min = Math.max(1, Math.round((r.dl - now) / 60000));
  const more = races.length > 1 ? "（ほか" + (races.length - 1) + "レース）" : "";
  return { t: "締切" + min + "分前｜" + name(p.j) + " " + p.rn + "R", b: hhmm(r.dl) + "締切" + more, u: "/racers/#v" + p.j + "r" + p.rn + "d" + p.hd, g: "dz-" + r.rid };
}

export function msgRes(items) {
  const r = items[0], p = parts(r.rid);
  const more = items.length > 1 ? "（ほか" + (items.length - 1) + "レース）" : "";
  return { t: "結果｜" + name(p.j) + " " + p.rn + "R", b: r.fin + (r.pay != null ? "　3連単 " + r.pay.toLocaleString("ja-JP") + "円" : "") + more, u: "/racers/#v" + p.j + "r" + p.rn + "d" + p.hd, g: "dz-r-" + r.rid };
}

async function kvGet(db, k) { const r = await db.prepare("SELECT v FROM kv WHERE k = ?1").bind(k).first(); return r ? r.v : null; }

async function deliver(db, sid, sub, payload, env, send, out) {
  let code = 0;
  try { code = await send(sub, JSON.stringify(payload), env.__jwk, env.VAPID_SUB); } catch (e) { code = -1; }
  if (code === 404 || code === 410) {
    out.gone++;
    await db.batch([db.prepare("DELETE FROM races WHERE sid = ?1").bind(sid), db.prepare("DELETE FROM daily WHERE sid = ?1").bind(sid), db.prepare("DELETE FROM subs WHERE id = ?1").bind(sid)]);
  } else if (code >= 200 && code < 300) out.sent++;
  else out.fail++;
}

export async function runOnce(env, now = Date.now(), send = sendPush, fetchFn = fetch) {
  const db = env.DZ_DB;
  if (!db || !env.VAPID_PRIVATE || !env.VAPID_SUB) return { skip: true };
  env.__jwk = typeof env.VAPID_PRIVATE === "string" ? JSON.parse(env.VAPID_PRIVATE) : env.VAPID_PRIVATE;
  const site = new URL(env.VAPID_SUB).origin;
  const out = { sent: 0, gone: 0, fail: 0, offi: 0, res: 0 };

  // ---- 10分前 ----
  const rows = (await db.prepare(
    "SELECT r.sid, r.rid, r.dl, s.ep, s.p256dh, s.auth FROM races r JOIN subs s ON s.id = r.sid WHERE r.m = 1 AND r.sent = 0 AND r.dl > ?1 AND r.dl <= ?2 ORDER BY r.sid, r.dl, r.rid"
  ).bind(now - 3600000, now + 45 * 60000).all()).results || [];
  // 公式の締切：締切40分前に入ったレースのある場だけ、3分おきに読む
  const want = new Map();
  for (const x of rows) { if (x.dl <= now + 40 * 60000) { const p = parts(x.rid); want.set(p.j + "_" + p.hd, p); } }
  const offi = new Map();
  if (want.size) {
    const keys = [...want.keys()];
    const have = (await db.prepare("SELECT jh, t, j FROM offi WHERE jh IN (SELECT value FROM json_each(?1))").bind(JSON.stringify(keys)).all()).results || [];
    for (const h of have) offi.set(h.jh, { t: h.t, j: JSON.parse(h.j) });
    const stale = keys.filter(k => !offi.has(k) || offi.get(k).t < now - OFFI_EVERY).sort((a, b) => (offi.get(a) ? offi.get(a).t : 0) - (offi.get(b) ? offi.get(b).t : 0)).slice(0, OFFI_MAX);
    for (const k of stale) {
      const p = want.get(k);
      try {
        const res = await fetchFn("https://www.boatrace.jp/owpc/pc/race/raceindex?jcd=" + p.j + "&hd=" + p.hd, { headers: { "user-agent": "Mozilla/5.0", "accept-language": "ja" } });
        if (!res.ok) continue;
        const j = parseOfficial(await res.text());
        if (!Object.keys(j).length) continue;
        offi.set(k, { t: now, j });
        out.offi++;
        await db.prepare("INSERT INTO offi (jh, t, j) VALUES (?1, ?2, ?3) ON CONFLICT(jh) DO UPDATE SET t = excluded.t, j = excluded.j").bind(k, now, JSON.stringify(j)).run();
      } catch (e) { /* 読めなければ出走表の時刻のまま */ }
    }
  }
  const fix = new Map(), due = new Map(), missed = [];
  for (const x of rows) {
    const p = parts(x.rid), o = offi.get(p.j + "_" + p.hd);
    let dl = x.dl;
    const t = o && o.j[+p.rn] ? toMs(p.hd, o.j[+p.rn]) : null;
    if (t && t !== dl) { dl = t; fix.set(x.rid, t); }
    if (dl <= now + 30000) { missed.push(x); continue; }
    if (dl - now <= LEAD_MS + 30000) {
      if (!due.has(x.sid)) due.set(x.sid, { sub: { ep: x.ep, p256dh: x.p256dh, auth: x.auth }, races: [] });
      due.get(x.sid).races.push({ rid: x.rid, dl });
    }
  }
  const st = [];
  for (const [rid, t] of fix) st.push(db.prepare("UPDATE races SET dl = ?2 WHERE rid = ?1").bind(rid, t));
  for (const x of missed) st.push(db.prepare("UPDATE races SET sent = 1 WHERE sid = ?1 AND rid = ?2").bind(x.sid, x.rid));
  for (const [sid, g] of due) for (const r of g.races) st.push(db.prepare("UPDATE races SET sent = 1 WHERE sid = ?1 AND rid = ?2").bind(sid, r.rid));
  if (st.length) await db.batch(st);
  for (const [sid, g] of due) { g.races.sort((a, b) => a.dl - b.dl || (a.rid < b.rid ? -1 : 1)); await deliver(db, sid, g.sub, msg10(g.races, now), env, send, out); }

  // ---- 結果 ----
  const rr = (await db.prepare(
    "SELECT r.sid, r.rid, r.dl, s.ep, s.p256dh, s.auth FROM races r JOIN subs s ON s.id = r.sid WHERE r.k = 1 AND r.sr = 0 AND r.dl <= ?1 ORDER BY r.sid, r.dl, r.rid"
  ).bind(now - 10 * 60000).all()).results || [];
  if (rr.length) {
    const days = [...new Set(rr.map(x => parts(x.rid).hd))];
    const text = new Map();
    for (const hd of days) {
      const last = Number(await kvGet(db, "res:" + hd) || 0);
      if (now - last < RES_EVERY) continue;
      await db.prepare("INSERT INTO kv (k, v) VALUES (?1, ?2) ON CONFLICT(k) DO UPDATE SET v = excluded.v").bind("res:" + hd, String(now)).run();
      try {
        const res = await fetchFn(site + "/results/data/" + hd + ".json?_=" + now, { cf: { cacheTtl: 0 } });
        if (res.ok) { text.set(hd, await res.text()); out.res++; }
      } catch (e) {}
    }
    const got = new Map(), done = [];
    for (const x of rr) {
      const p = parts(x.rid), t = text.get(p.hd);
      const f = t ? findResult(t, p.j, p.rn) : null;
      if (f) {
        if (!got.has(x.sid)) got.set(x.sid, { sub: { ep: x.ep, p256dh: x.p256dh, auth: x.auth }, items: [] });
        got.get(x.sid).items.push({ rid: x.rid, fin: f.fin, pay: f.pay });
        done.push(x);
      } else if (now - x.dl > RES_GIVEUP) done.push(x);
    }
    if (done.length) await db.batch(done.map(x => db.prepare("UPDATE races SET sr = 1 WHERE sid = ?1 AND rid = ?2").bind(x.sid, x.rid)));
    for (const [sid, g] of got) await deliver(db, sid, g.sub, msgRes(g.items), env, send, out);
  }

  // ---- 片づけ：締切から1日たったレース、30日使われていない購読、古い公式の写し ----
  if (new Date(now).getUTCMinutes() % 30 === 0) {
    await db.batch([
      db.prepare("DELETE FROM races WHERE dl < ?1").bind(now - 86400000),
      db.prepare("DELETE FROM daily WHERE day < ?1").bind(jstDay(now - 2 * 86400000)),
      db.prepare("DELETE FROM races WHERE sid IN (SELECT id FROM subs WHERE seen < ?1)").bind(now - 30 * 86400000),
      db.prepare("DELETE FROM subs WHERE seen < ?1").bind(now - 30 * 86400000),
      db.prepare("DELETE FROM offi WHERE t < ?1").bind(now - 2 * 86400000),
      db.prepare("DELETE FROM kv WHERE k LIKE 'res:%' AND CAST(v AS INTEGER) < ?1").bind(now - 2 * 86400000),
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
