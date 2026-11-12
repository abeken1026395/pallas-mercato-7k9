// Web Push の送信（RFC 8291 の aes128gcm 暗号化＋RFC 8292 の VAPID 署名）。外部の部品を使わず WebCrypto だけで作る。
// 使う場所：プッシュ通知の送り役（edge/pushWorker.mjs）。試験は edge/webPush.test.mjs。
const te = new TextEncoder();

export function b64u(buf) {
  const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function unb64u(s) {
  const t = String(s).replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(t + "===".slice((t.length + 3) % 4));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function cat(...parts) {
  const n = parts.reduce((a, p) => a + p.length, 0);
  const out = new Uint8Array(n);
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

async function hmac(key, data) {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, data));
}

// HKDF（抽出と展開。長さは32バイト以下だけ使う）
async function hkdf(salt, ikm, info, len) {
  const prk = await hmac(salt, ikm);
  const okm = await hmac(prk, cat(info, new Uint8Array([1])));
  return okm.slice(0, len);
}

// 本文を購読者の鍵で暗号化する。返り値はそのまま POST の本文にする
export async function encrypt(payload, p256dhB64, authB64, opt = {}) {
  const uaPub = unb64u(p256dhB64);
  const authSecret = unb64u(authB64);
  if (uaPub.length !== 65 || authSecret.length !== 16) throw new Error("購読の鍵の長さが違う");
  const asKeys = opt.asKeys || await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const asPub = new Uint8Array(await crypto.subtle.exportKey("raw", asKeys.publicKey));
  const uaKey = await crypto.subtle.importKey("raw", uaPub, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: uaKey }, asKeys.privateKey, 256));
  const ikm = await hkdf(authSecret, shared, cat(te.encode("WebPush: info\0"), uaPub, asPub), 32);
  const salt = opt.salt || crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(salt, ikm, te.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(salt, ikm, te.encode("Content-Encoding: nonce\0"), 12);
  const plain = cat(te.encode(payload), new Uint8Array([2]));
  const k = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, k, plain));
  const rs = new Uint8Array([0, 0, 16, 0]); // 記録の大きさ 4096
  return cat(salt, rs, new Uint8Array([asPub.length]), asPub, ct);
}

// VAPID の署名（JWT・ES256）。privJwk は P-256 の秘密鍵（JWK）
export async function vapidAuth(endpoint, privJwk, subject, now = Date.now()) {
  const aud = new URL(endpoint).origin;
  const header = b64u(te.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const body = b64u(te.encode(JSON.stringify({ aud, exp: Math.floor(now / 1000) + 12 * 3600, sub: subject })));
  const key = await crypto.subtle.importKey("jwk", privJwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, te.encode(header + "." + body)));
  const pub = b64u(cat(new Uint8Array([4]), unb64u(privJwk.x), unb64u(privJwk.y)));
  return "vapid t=" + header + "." + body + "." + b64u(sig) + ", k=" + pub;
}

// 1通送る。返り値は HTTP の状態番号（404・410 は購読が消えた）
export async function sendPush(sub, payload, privJwk, subject, fetchFn = fetch) {
  const body = await encrypt(payload, sub.p256dh, sub.auth);
  const res = await fetchFn(sub.ep, {
    method: "POST",
    headers: {
      "Authorization": await vapidAuth(sub.ep, privJwk, subject),
      "Content-Encoding": "aes128gcm",
      "Content-Type": "application/octet-stream",
      "TTL": "600",
      "Urgency": "high",
    },
    body,
  });
  return res.status;
}
