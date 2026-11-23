// 自動ブロック（2026-11-23 けん「巡回がbot見つけたら自動的にブロックしまくる仕組みにしろ」）
// 決まり：Cookie を一度も持ち帰らずに、短い時間に多くのページを開いた接続元は機械とみなし、アクセスを拒否する。
// - 接続元（日替わりの変換後）は、その日（JST）のうち拒否する
// - 名乗りと回線の組み合わせは、決められた日数だけ拒否する（接続元を毎回変えて来る相手を、翌日の1回目から止める）
// しきい値は Pages の秘密の環境変数 DZ_BAN（「ページ数,秒数,日数」）にだけ置く。無ければ自動ブロックは動かない。
// 記録先は D1（バインディング DZ_DB）の表 junkaiHit・junkaiBan。読めない・書けないときは何もしない（本物を返す）。
import { hashIp, pathKind } from "./junkai.mjs";
import { trapCfg } from "./trapCfg.mjs";


export const SQL = {
  isBanned: "SELECT k FROM junkaiBan WHERE k IN (?1, ?2) AND until > ?3 LIMIT 1",
  addHit: "INSERT INTO junkaiHit (k, t) VALUES (?1, ?2)",
  countHit: "SELECT COUNT(*) AS n FROM junkaiHit WHERE k = ?1 AND t > ?2",
  addBan: "INSERT OR REPLACE INTO junkaiBan (k, kind, until, ua, asn, at) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
  sweep: "DELETE FROM junkaiHit WHERE t < ?1",
};

export function banConfig(env) {
  const m = /^(\d+),(\d+),(\d+)$/.exec(String((env && env.DZ_BAN) || "").trim());
  if (!m) return null;
  const pages = Number(m[1]), sec = Number(m[2]), days = Number(m[3]);
  if (!(pages >= 2 && sec >= 10 && days >= 0)) return null;
  return { pages, sec, days };
}

async function sha16(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

export async function fpKey(ua, asn) {
  return "f" + (await sha16("fp|" + ua + "|" + asn));
}

// JST の翌日0時（UNIX秒）
export function jstDayEnd(nowSec) {
  const j = nowSec + 9 * 3600;
  return (Math.floor(j / 86400) + 1) * 86400 - 9 * 3600;
}

// 戻り値：true＝拒否する
export async function checkBan(context, vc, now = Date.now()) {
  try {
    const env = context.env;
    const cfg = banConfig(env);
    if (!cfg || !env.DZ_DB || !env.DZ_SALT) return false;
    const db = env.DZ_DB;
    const { request } = context;
    const nowSec = Math.floor(now / 1000);
    const ua = (request.headers.get("user-agent") || "").slice(0, 120);
    const asn = String((request.cf && request.cf.asn) || 0);
    const ip = "i" + (await hashIp(request.headers.get("cf-connecting-ip") || "", env.DZ_SALT, now));
    const fp = await fpKey(ua, asn);
    const hit = await db.prepare(SQL.isBanned).bind(ip, fp, nowSec).first();
    if (hit) return true;
    if (!vc.isNew || pathKind(new URL(request.url).pathname) !== "page") return false;
    await db.prepare(SQL.addHit).bind(ip, nowSec).run();
    const row = await db.prepare(SQL.countHit).bind(ip, nowSec - cfg.sec).first();
    if (Math.random() < 0.02) await db.prepare(SQL.sweep).bind(nowSec - 2 * cfg.sec).run();
    if (!row || Number(row.n) < cfg.pages) return false;
    await db.prepare(SQL.addBan).bind(ip, "ip", jstDayEnd(nowSec), ua, asn, nowSec).run();
    const chk = trapCfg(context.env).chk;
    if (!(chk && ua === chk) && cfg.days > 0) {
      await db.prepare(SQL.addBan).bind(fp, "fp", nowSec + cfg.days * 86400, ua, asn, nowSec).run();
    }
    return true;
  } catch (e) {
    return false;
  }
}
