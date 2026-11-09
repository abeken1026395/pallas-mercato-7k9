// 連続巡回の記録（2026-11-09 けん裁定）。まず記録だけを1〜2週間取り、実測を見て上限を決める。
// 数える単位は「接続元」と「Cookie」の両方。
// - 接続元はそのまま残さない。日替わりの鍵（Pages の秘密の環境変数 DZ_SALT＋JSTの日付）で変換した16桁だけを残す。
//   IPv6 は端末ごとに末尾が変わるので、先頭の4区切り（/64）で数える。
// - Cookie は dzv（ランダムな16桁・1年）。計測の端末内保存（localStorage の dzRaihou）とは別物で、互いに触らない。
// 記録先は Analytics Engine（バインディング名 DZ_LOG）。無い・失敗したときは何もしない（ページは止めない・中身は変えない）。

const COOKIE = "dzv";
const ID_RE = /^[0-9a-f]{16}$/;

function hex(bytes) {
  return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
}

export function visitorCookie(request) {
  const raw = request.headers.get("cookie") || "";
  for (const part of raw.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === COOKIE && ID_RE.test(v.join("="))) return { id: v.join("="), isNew: false };
  }
  return { id: hex(crypto.getRandomValues(new Uint8Array(8))), isNew: true };
}

export function ipKey(ip) {
  if (!ip) return "";
  if (ip.includes(":")) return ip.toLowerCase().split(":").slice(0, 4).join(":") + "::/64";
  return ip;
}

export function jstDay(now = Date.now()) {
  return new Date(now + 9 * 3600000).toISOString().slice(0, 10);
}

export function pathKind(pathname) {
  const last = pathname.split("/").pop();
  return (last === "" || !last.includes(".") || last.endsWith(".html")) ? "page" : "data";
}

async function hashIp(ip, salt, day) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(salt + "|" + day + "|" + ipKey(ip)));
  return hex(new Uint8Array(buf)).slice(0, 16);
}

export async function recordVisit(context, vc, trapped, now = Date.now()) {
  try {
    const env = context.env;
    if (!env || !env.DZ_LOG || !env.DZ_SALT) return false;
    const { request } = context;
    const url = new URL(request.url);
    const ip = request.headers.get("cf-connecting-ip") || "";
    const cf = request.cf || {};
    const h = await hashIp(ip, env.DZ_SALT, jstDay(now));
    env.DZ_LOG.writeDataPoint({
      indexes: [h],
      blobs: [
        h,                                                    // 1 接続元（変換後）
        vc.id,                                                // 2 Cookie
        vc.isNew ? "new" : "known",                           // 3 Cookie を持って来たか
        url.pathname.slice(0, 200),                           // 4 パス
        pathKind(url.pathname),                               // 5 ページかデータか
        (request.headers.get("user-agent") || "").slice(0, 120), // 6 名乗り
        String(cf.asn || 0),                                  // 7 回線の持ち主の番号
        String(cf.colo || ""),                                // 8 受けた拠点
        trapped ? "trap" : "real",                            // 9 罠を返したか
      ],
      doubles: [1],
    });
    return true;
  } catch (e) {
    return false;
  }
}

export function withCookie(res, vc) {
  if (!vc.isNew) return res;
  try {
    const out = new Response(res.body, res);
    out.headers.append("set-cookie", `${COOKIE}=${vc.id}; Path=/; Max-Age=31536000; SameSite=Lax; Secure; HttpOnly`);
    return out;
  } catch (e) {
    return res;
  }
}
