// 再訪設計 5章「測るもの」の回数だけを数える（2026-11-20 けん「承認」）。
// 受け取るのは種類の名前1つだけ。日本時間の日付と種類ごとに回数を1つ足す。
// 接続元・端末の番号・Cookie・買い目・金額は受け取らず、残さない。
// 種類：save（買い目を新しく保存した）／o10（10分前・推しの通知を開いた）／oRes（レースごとの結果の通知を開いた）／
//       oSum（その日のまとめの通知を開いた）／off（通知を切った）／note（note へのリンクを押した）
import { jstDay } from "./junkai.mjs";
import { json, sameOrigin } from "./live.mjs";

export const KINDS = ["save", "o10", "oRes", "oSum", "off", "note"];
export const SCHEMA_KAZU = "CREATE TABLE IF NOT EXISTS kazu (day TEXT NOT NULL, k TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, k))";

export async function onKazu(context, now = Date.now()) {
  const { request, env } = context;
  if (request.method !== "POST") return json({ ok: false }, 405);
  if (!sameOrigin(request)) return json({ ok: false }, 403);
  const db = env && env.DZ_DB;
  if (!db) return json({ ok: true, skip: 1 });
  let body = "";
  try { body = (await request.text()).slice(0, 200); } catch (e) { body = ""; }
  let k = "";
  try { const o = JSON.parse(body); k = o && typeof o.k === "string" ? o.k : ""; } catch (e) { k = ""; }
  if (KINDS.indexOf(k) < 0) return json({ ok: false }, 400);
  try {
    await db.prepare("INSERT INTO kazu (day, k, n) VALUES (?1, ?2, 1) ON CONFLICT(day, k) DO UPDATE SET n = n + 1").bind(jstDay(now), k).run();
  } catch (e) {
    return json({ ok: false }, 503);
  }
  return json({ ok: true });
}
