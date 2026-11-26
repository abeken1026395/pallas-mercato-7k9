// 入口：見分けは別の部品（サービス結合 DZ_GUARD）に任せ、その答えに従う。
// 答えが「通す」なら本物を返し、部品が付けた Cookie だけ写す。部品が無い・答えないときは本物を返す。
// （ファイル名 _middleware.js は Cloudflare Pages の決まりなので変えない）
const FWD = ["DZ_SALT", "DZ_BAN", "DZ_TS_SITEKEY", "DZ_TS_SECRET", "DZ_GATE_SIGN", "DZ_GATE_KEY", "DZ_GATE_CAP", "DZ_DECOY", "DZ_TRAP"];

export async function onRequest(context) {
  const { request, env } = context;
  if (new URL(request.url).pathname.startsWith("/api/")) return context.next();
  const guard = env && env.DZ_GUARD;
  if (!guard) return context.next();
  let ans;
  try {
    const fwd = {};
    for (const k of FWD) if (env[k] !== undefined) fwd[k] = env[k];
    const cf = request.cf || {};
    const h = new Headers(request.headers);
    h.set("x-dz-env", JSON.stringify(fwd));
    h.set("x-dz-cf", JSON.stringify({ asn: cf.asn, country: cf.country, colo: cf.colo }));
    const init = { method: request.method, headers: h };
    if (request.method !== "GET" && request.method !== "HEAD") init.body = await request.clone().arrayBuffer();
    ans = await guard.fetch(new Request(request.url, init));
  } catch (e) {
    return context.next();
  }
  if (ans.status >= 500) return context.next();
  if (ans.headers.get("x-dz-pass") !== "1") return ans;
  const tail = ans.headers.get("x-dz-tail");
  const head = ans.headers.get("x-dz-head");
  let res = null;
  // HTML を足すページは、手元の写しとの照合（304）にせず、毎回まるごと返す
  if ((tail || head) && request.method === "GET") {
    try {
      const h2 = new Headers(request.headers);
      h2.delete("if-none-match"); h2.delete("if-modified-since");
      res = await context.next(new Request(request, { headers: h2 }));
    } catch (e) { res = null; }
  }
  if (!res) res = await context.next();
  const cookies = typeof ans.headers.getSetCookie === "function" ? ans.headers.getSetCookie() : [];
  if (!cookies.length && !tail && !head) return res;
  let out = new Response(res.body, res);
  for (const c of cookies) out.headers.append("set-cookie", c);
  // 部品が渡した HTML があれば、ページの先頭（head）と末尾（body）に足す。足せないときは何もしない
  if ((tail || head) && res.status === 200 && (res.headers.get("content-type") || "").includes("text/html") && typeof HTMLRewriter !== "undefined") {
    try {
      const t = tail ? decodeURIComponent(tail) : "", hd = head ? decodeURIComponent(head) : "";
      let rw = new HTMLRewriter();
      if (hd) rw = rw.on("head", { element(el) { el.prepend(hd, { html: true }); } });
      if (t) rw = rw.on("body", { element(el) { el.append(t, { html: true }); } });
      out = rw.transform(out);
    } catch (e) { /* 足せなければそのまま返す */ }
  }
  return out;
}
