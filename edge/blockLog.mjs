// 拒否した相手の記録（2026-11-23 けん裁定）：拒否した相手だけ、接続元をそのまま非公開の記録に残す。
// 普通の来訪者は残さない。記録の失敗で応答を止めない。古い記録は90日で消す。
const KEEP_MS = 90 * 24 * 3600 * 1000;

export async function logBlock(context, why, now = Date.now()) {
  const db = context.env && context.env.DZ_DB;
  if (!db) return;
  const req = context.request;
  const cf = req.cf || {};
  const ip = req.headers.get("cf-connecting-ip") || "";
  const ua = (req.headers.get("user-agent") || "").slice(0, 300);
  const path = new URL(req.url).pathname.slice(0, 200);
  const job = (async () => {
    try {
      await db.prepare("INSERT INTO blockLog (t, ip, ua, asn, colo, country, path, why) VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
        .bind(now, ip, ua, cf.asn || 0, cf.colo || "", cf.country || "", path, why).run();
      if (Math.random() < 0.02) await db.prepare("DELETE FROM blockLog WHERE t < ?").bind(now - KEEP_MS).run();
    } catch (e) { /* 記録の失敗は無視する */ }
  })();
  if (typeof context.waitUntil === "function") context.waitUntil(job); else await job;
}
