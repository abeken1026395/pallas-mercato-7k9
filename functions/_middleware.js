// Cloudflare Pages Functions：AIの取得役（名乗りか回線で判定）には、対象ページの本物を返さず、冗談の出走表だけを返す。
// 人間・判定できない相手には context.next() の本物をそのまま返す。
// （ファイル名 _middleware.js は Cloudflare Pages の決まりなので変えない）
import { isAiAgent, isAiNetwork, noticeKind, noticeResponse } from "../edge/aiNotice.mjs";

export async function onRequest(context) {
  const { request } = context;
  const ua = request.headers.get("user-agent") || "";
  const asn = (request.cf && request.cf.asn) || 0;   // 回線の持ち主の番号（Cloudflare が付ける）
  if (request.method === "GET" || request.method === "HEAD") {
    if (isAiAgent(ua) || isAiNetwork(asn)) {
      const pathname = new URL(request.url).pathname;
      const kind = noticeKind(pathname);
      // 本物を読み込む前に返す（本物には一切触れない・処理も軽い）
      if (kind) return noticeResponse(kind, pathname);
    }
  }
  return context.next();
}
