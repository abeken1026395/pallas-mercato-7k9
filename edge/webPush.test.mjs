// 動かし方：npm i http_ece のあと node --test edge/webPush.test.mjs（配信WFの試験には入れていない）
// 暗号化と署名の試験。暗号化は http_ece（Mozilla の参照実装）で復号して元に戻るか、署名は web-push の鍵で検証できるかを見る
import test from "node:test";
import assert from "node:assert";
import { createRequire } from "node:module";
import { encrypt, vapidAuth, unb64u, b64u } from "./webPush.mjs";
const require = createRequire(import.meta.url);

test("aes128gcm で暗号化した本文を参照実装で復号できる", async () => {
  const ece = require("http_ece");
  const ecdh = require("node:crypto").createECDH("prime256v1");
  ecdh.generateKeys();
  const auth = require("node:crypto").randomBytes(16);
  const msg = JSON.stringify({ t: "締切10分前", b: "住之江 5R（15:30締切）", u: "/racers/#v12r5d20261113" });
  const body = await encrypt(msg, b64u(ecdh.getPublicKey()), b64u(auth));
  const out = ece.decrypt(Buffer.from(body), { version: "aes128gcm", privateKey: ecdh, authSecret: auth });
  assert.strictEqual(out.toString("utf8"), msg);
});

test("VAPID の署名を公開鍵で検証できる", async () => {
  const kp = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
  const jwk = await crypto.subtle.exportKey("jwk", kp.privateKey);
  const h = await vapidAuth("https://web.push.apple.com/abc", jwk, "https://example.test/", Date.UTC(2026, 10, 13));
  const m = h.match(/^vapid t=([^.]+)\.([^.]+)\.([^,]+), k=(.+)$/);
  assert.ok(m);
  const claims = JSON.parse(new TextDecoder().decode(unb64u(m[2])));
  assert.strictEqual(claims.aud, "https://web.push.apple.com");
  const ok = await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, kp.publicKey, unb64u(m[3]), new TextEncoder().encode(m[1] + "." + m[2]));
  assert.ok(ok);
  assert.strictEqual(unb64u(m[4]).length, 65);
});

test("鍵の長さが違う購読は止める", async () => {
  await assert.rejects(encrypt("x", b64u(new Uint8Array(10)), b64u(new Uint8Array(16))));
});
