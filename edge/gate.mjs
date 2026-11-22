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

export async function makePass(signKey, now = Date.now()) {
  const exp = Math.floor(now / 1000) + GATE_DAYS * 86400;
  return exp + "." + (await hmac(signKey, "dzg|" + exp));
}

export async function validPass(signKey, value, now = Date.now()) {
  const m = /^(\d{10})\.([0-9a-f]{64})$/.exec(value || "");
  if (!m) return false;
  if (Number(m[1]) <= Math.floor(now / 1000)) return false;
  const want = await hmac(signKey, "dzg|" + m[1]);
  let d = 0;
  for (let i = 0; i < 64; i++) d |= want.charCodeAt(i) ^ m[2].charCodeAt(i);
  return d === 0;
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
export async function gateOff(env) {
  try {
    if (!env.DZ_DB) return false;
    const row = await env.DZ_DB.prepare("SELECT v FROM kv WHERE k = 'gate:off'").first();
    return !!(row && String(row.v) === "1");
  } catch (e) {
    return false;
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
      const pass = await makePass(env.DZ_GATE_SIGN, now);
      return new Response("OK", { status: 200, headers: { ...H, "set-cookie": `${GATE_COOKIE}=${pass}; Path=/; Max-Age=${GATE_DAYS * 86400}; SameSite=Lax; Secure; HttpOnly` } });
    }
    if (isOpenPath(url.pathname)) return null;
    if (await gateOff(env)) return null;
    if (keyOk(request, env)) return null;
    if (await validPass(env.DZ_GATE_SIGN, readCookie(request, GATE_COOKIE), now)) return null;
    if (pathKind(url.pathname) === "page" && (request.method === "GET" || request.method === "HEAD")) {
      return new Response(gatePage(env.DZ_TS_SITEKEY), { status: 403, headers: { ...H, "content-type": "text/html; charset=utf-8" } });
    }
    return new Response("Forbidden", { status: 403, headers: { ...H, "content-type": "text/plain; charset=utf-8" } });
  } catch (e) {
    return null;
  }
}
