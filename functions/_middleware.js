// Cloudflare Pages Functions：AIの取得役にだけ囮を返す（第1段 /racers/・/players/card.html）。
// /racers/ は HTML に埋め込まれた出走表（var RAW）も CSV と同じ囮に置き換える。
// 人間・判定できない相手には context.next() の本物をそのまま返す。
import { isAiAgent, decoyKind, decoyRacersCsv, decoyRacersHtml, decoyJson, injectNotice } from "../edge/decoy.mjs";

export async function onRequest(context) {
  const { request } = context;
  const res = await context.next();
  const ua = request.headers.get("user-agent") || "";
  if (!isAiAgent(ua) || request.method !== "GET" || res.status !== 200) return res;

  const url = new URL(request.url);
  const kind = decoyKind(url.pathname);
  if (!kind) return res;

  let body;
  try {
    // BOM も本物どおり残す（形式を本物と揃える）
    const text = new TextDecoder("utf-8", { ignoreBOM: true }).decode(await res.arrayBuffer());
    if (kind === "html") body = injectNotice(text);
    // 出走表 HTML は本物の出走表を var RAW = {...} で丸ごと埋め込んでいるので、それも囮にする。
    else if (kind === "racersHtml") body = injectNotice(decoyRacersHtml(text));
    else if (kind === "racersCsv") body = decoyRacersCsv(text);
    else body = JSON.stringify(decoyJson(JSON.parse(text), url.pathname, url.pathname));
  } catch (e) {
    // 囮を作れないときは何も返さない（本物を渡さない）。
    return new Response("", { status: 503 });
  }
  const headers = new Headers(res.headers);
  headers.delete("content-length");
  headers.delete("etag");
  headers.set("cache-control", "private, no-store");
  headers.set("vary", "User-Agent");
  return new Response(body, { status: 200, headers });
}
