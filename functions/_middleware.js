// Cloudflare Pages Functions：AIの取得役には、対象ページの本物を返さず、通告と冗談の数字だけを返す。
// 人間・判定できない相手には context.next() の本物をそのまま返す。
// （ファイル名 _middleware.js は Cloudflare Pages の決まりなので変えない）
import { isAiAgent, noticeKind, noticeResponse } from "../edge/aiNotice.mjs";

export async function onRequest(context) {
  const { request } = context;
  const ua = request.headers.get("user-agent") || "";
  if (request.method === "GET" || request.method === "HEAD") {
    if (isAiAgent(ua)) {
      const pathname = new URL(request.url).pathname;
      const kind = noticeKind(pathname);
      // 本物を読み込む前に返す（本物には一切触れない・処理も軽い）
      if (kind) return noticeResponse(kind, pathname);
    }
  }
  return context.next();
}
