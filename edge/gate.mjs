// 人間確認の関門（2026-11-23 けん「私はロボットではありませんのやつ」・案A）
// 合格の印（署名つき Cookie dzg）が無い相手には、ページなら確認画面、データなら403を返す。
// 確認は Cloudflare Turnstile。サイト用の鍵 DZ_TS_SITEKEY・秘密の鍵 DZ_TS_SECRET・印の署名の鍵 DZ_GATE_SIGN は Pages の秘密の値にだけ置く。
// どれかが無いときは関門を開けたままにする（読者を締め出さない側に倒す）。
// 通知の送り役（Worker dz-push）は、秘密の合図 x-dz-key（DZ_GATE_KEY）で通す。
import { pathKind } from "./junkai.mjs";

export const GATE_COOKIE = "dzg";
export const GATE_DAYS = 30;
export const VERIFY_PATH = "/__gate/verify";

// 関門の外：告知の入口とカード画像、見た目の部品、通知の受け口、関門そのもの、利用規約
const OPEN = [/^\/in\//, /^\/assets\//, /^\/api\//, /^\/__gate\//, /^\/ogp[^/]*\.(png|jpg)$/, /^\/favicon[^/]*$/, /^\/sw\.js$/, /^\/manifest[^/]*$/, /^\/robots\.txt$/, /^\/kiyaku\//];

export function isOpenPath(pathname) {
  return OPEN.some(re => re.test(pathname));
}

export function gateReady(env) {
  return !!(env && env.DZ_TS_SITEKEY && env.DZ_TS_SECRET && env.DZ_GATE_SIGN);
}

async function hmac(key, msg) {
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(msg));
  return Array.from(new Uint8Array(sig), b => b.toString(16).padStart(2, "0")).join("");
}

// 印は、通ったときの名乗りと回線にひもづける（2026-11-23 けん「1だけ」）。別の機械・回線に写しても使えない
export async function bindOf(ua, asn) {
  return (await hmac("bind", "b|" + (ua || "") + "|" + String(asn || 0))).slice(0, 8);
}

export async function makePass(signKey, now = Date.now(), bind = "00000000") {
  const exp = Math.floor(now / 1000) + GATE_DAYS * 86400;
  return exp + "." + bind + "." + (await hmac(signKey, "dzg|" + exp + "|" + bind));
}

// 戻り値：印の番号（署名の先頭16桁）か ""（無効）
export async function validPass(signKey, value, now = Date.now(), bind = "00000000") {
  const m = /^(\d{10})\.([0-9a-f]{8})\.([0-9a-f]{64})$/.exec(value || "");
  if (!m) return "";
  if (Number(m[1]) <= Math.floor(now / 1000)) return "";
  if (m[2] !== bind) return "";
  const want = await hmac(signKey, "dzg|" + m[1] + "|" + m[2]);
  let d = 0;
  for (let i = 0; i < 64; i++) d |= want.charCodeAt(i) ^ m[3].charCodeAt(i);
  return d === 0 ? m[3].slice(0, 16) : "";
}

// 印ごとの量の上限：DZ_GATE_CAP（「ページ数,秒数」）は Pages の秘密の値にだけ置く。超えた印は無効にして関門からやり直させる
// 記録先は D1 の表 gateUse・gateBan。読めない・書けないときは止めない
export function capConfig(env) {
  const m = /^(\d+),(\d+)$/.exec(String((env && env.DZ_GATE_CAP) || "").trim());
  if (!m) return null;
  const pages = Number(m[1]), sec = Number(m[2]);
  return pages >= 10 && sec >= 10 ? { pages, sec } : null;
}

// 戻り値：true＝この印は無効（取り消し済み、または今回で上限を超えた）
export async function passOverCap(env, id, isPage, exp, now = Date.now()) {
  try {
    const cfg = capConfig(env);
    if (!cfg || !env.DZ_DB || !id) return false;
    const db = env.DZ_DB;
    const t = Math.floor(now / 1000);
    if (await db.prepare("SELECT p FROM gateBan WHERE p = ?1 AND until > ?2 LIMIT 1").bind(id, t).first()) return true;
    if (!isPage) return false;
    await db.prepare("INSERT INTO gateUse (p, t) VALUES (?1, ?2)").bind(id, t).run();
    const row = await db.prepare("SELECT COUNT(*) AS n FROM gateUse WHERE p = ?1 AND t > ?2").bind(id, t - cfg.sec).first();
    if (Math.random() < 0.01) await db.prepare("DELETE FROM gateUse WHERE t < ?1").bind(t - 2 * cfg.sec).run();
    if (!row || Number(row.n) <= cfg.pages) return false;
    await db.prepare("INSERT OR REPLACE INTO gateBan (p, until) VALUES (?1, ?2)").bind(id, exp).run();
    return true;
  } catch (e) {
    return false;
  }
}

function readCookie(request, name) {
  for (const part of (request.headers.get("cookie") || "").split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return v.join("=");
  }
  return "";
}

function keyOk(request, env) {
  const k = request.headers.get("x-dz-key") || "";
  return !!(env.DZ_GATE_KEY && k && k === env.DZ_GATE_KEY);
}

const H = { "cache-control": "private, no-store", "x-robots-tag": "noindex" };

function escapeAttr(s) {
  return String(s).replace(/[&"<>]/g, c => ({ "&": "&amp;", '"': "&quot;", "<": "&lt;", ">": "&gt;" }[c]));
}

export function gatePage(sitekey) {
  return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>確認しています</title>
<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f1115;color:#e8e8ea;font-family:system-ui,-apple-system,"Hiragino Sans",sans-serif}main{text-align:center;padding:24px}p{font-size:15px;line-height:1.7;margin:0 0 16px}#e{color:#ff7b7b;font-size:13px;min-height:1.5em}</style>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script></head><body><main>
<p>人による閲覧かを確認しています。<br>しばらくお待ちください。</p>
<div class="cf-turnstile" data-sitekey="${escapeAttr(sitekey)}" data-language="ja" data-callback="dzOk" data-error-callback="dzNg"></div>
<p id="e"></p></main>
<script>
function dzNg(){document.getElementById("e").textContent="確認できませんでした。ページを開き直してください。";}
function dzOk(t){fetch("${VERIFY_PATH}",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:"t="+encodeURIComponent(t),credentials:"same-origin"}).then(function(r){if(r.ok){location.reload();}else{dzNg();}}).catch(dzNg);}
</script></body></html>`;
}

export async function siteverify(secret, token, ip, fetchFn = fetch) {
  const body = new URLSearchParams({ secret, response: token });
  if (ip) body.set("remoteip", ip);
  const r = await fetchFn("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body });
  const j = await r.json();
  return !!(j && j.success);
}

// 非常口：D1（DZ_DB）の表 kv に k='gate:off', v='1' があれば関門を開ける（統括が Cloudflare からすぐ切り替えられる）
export async function flagOn(env, key) {
  try {
    if (!env.DZ_DB) return false;
    if (key !== "gate:off" && key !== "geo:off") return false;
    const row = await env.DZ_DB.prepare(`SELECT v FROM kv WHERE k = '${key}'`).first();
    return !!(row && String(row.v) === "1");
  } catch (e) {
    return false;
  }
}

export async function gateOff(env) {
  return flagOn(env, "gate:off");
}

// 海外からのアクセスを拒否する（2026-11-23 けん「入れて」）。Cloudflare が判定した国が日本以外なら403。
// 国が分からないときは止めない。関門の外（OPEN）と秘密の合図は通す。kv の geo:off=1 で止められる（非常口）
export function geoPage() {
  return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>ご利用いただけません</title>
<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f1115;color:#e8e8ea;font-family:system-ui,-apple-system,"Hiragino Sans",sans-serif}p{font-size:15px;line-height:1.7;text-align:center;padding:24px}</style>
</head><body><p>このサイトは日本国内からのみご利用いただけます。</p></body></html>`;
}

export async function geoBlock(context) {
  try {
    const { request } = context;
    const env = context.env || {};
    const country = request.cf && request.cf.country;
    if (!country || country === "JP") return null;
    const url = new URL(request.url);
    if (isOpenPath(url.pathname)) return null;
    if (keyOk(request, env)) return null;
    if (await flagOn(env, "geo:off")) return null;
    if (pathKind(url.pathname) === "page" && (request.method === "GET" || request.method === "HEAD")) {
      return new Response(geoPage(), { status: 403, headers: { ...H, "content-type": "text/html; charset=utf-8" } });
    }
    return new Response("Forbidden", { status: 403, headers: { ...H, "content-type": "text/plain; charset=utf-8" } });
  } catch (e) {
    return null;
  }
}

// 戻り値：Response（関門で止めた・確認の受け口）か null（通す）
export async function gate(context, fetchFn = fetch, now = Date.now()) {
  try {
    const { request } = context;
    const env = context.env || {};
    if (!gateReady(env)) return null;
    const url = new URL(request.url);
    if (url.pathname === VERIFY_PATH && request.method === "POST") {
      const form = await request.formData();
      const t = String(form.get("t") || "");
      const ok = t && await siteverify(env.DZ_TS_SECRET, t, request.headers.get("cf-connecting-ip") || "", fetchFn);
      if (!ok) return new Response("NG", { status: 403, headers: H });
      const bind = await bindOf(request.headers.get("user-agent") || "", request.cf && request.cf.asn);
      const pass = await makePass(env.DZ_GATE_SIGN, now, bind);
      return new Response("OK", { status: 200, headers: { ...H, "set-cookie": `${GATE_COOKIE}=${pass}; Path=/; Max-Age=${GATE_DAYS * 86400}; SameSite=Lax; Secure; HttpOnly` } });
    }
    if (isOpenPath(url.pathname)) return null;
    if (await gateOff(env)) return null;
    if (keyOk(request, env)) return null;
    const raw = readCookie(request, GATE_COOKIE);
    const bind = await bindOf(request.headers.get("user-agent") || "", request.cf && request.cf.asn);
    const id = await validPass(env.DZ_GATE_SIGN, raw, now, bind);
    const isPage = pathKind(url.pathname) === "page";
    if (id && !(await passOverCap(env, id, isPage, Number(raw.slice(0, 10)), now))) return null;
    if (isPage && (request.method === "GET" || request.method === "HEAD")) {
      return new Response(gatePage(env.DZ_TS_SITEKEY), { status: 403, headers: { ...H, "content-type": "text/html; charset=utf-8" } });
    }
    return new Response("Forbidden", { status: 403, headers: { ...H, "content-type": "text/plain; charset=utf-8" } });
  } catch (e) {
    return null;
  }
}
