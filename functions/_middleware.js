// Cloudflare Pages Functions：AIの取得役（名乗り・回線・言語の設定で判定）には、対象ページの本物を返さず、冗談の出走表だけを返す。
// 人間・判定できない相手には context.next() の本物をそのまま返す。
// あわせて、連続巡回の上限を決めるための記録だけを取る（2026-11-09 けん裁定：まず記録のみ・数える単位は接続元とCookie）。
// 記録は返す中身を一切変えない。記録の失敗でページを止めない。
// （ファイル名 _middleware.js は Cloudflare Pages の決まりなので変えない）
import { isAiAgent, isAiNetwork, lacksJapanese, noticeKind, noticeResponse, isScraper, blockResponse } from "../edge/aiNotice.mjs";
import { visitorCookie, recordVisit, withCookie } from "../edge/junkai.mjs";
import { checkBan } from "../edge/ban.mjs";
import { gate, geoBlock } from "../edge/gate.mjs";

export async function onRequest(context) {
  const { request } = context;
  // 今見ている人数・プッシュ通知の受け口（/api/）は罠も記録も通さない（2026-11-13・ページの合図を来訪として数えない）
  if (new URL(request.url).pathname.startsWith("/api/")) return context.next();
  const ua = request.headers.get("user-agent") || "";
  const asn = (request.cf && request.cf.asn) || 0;   // 回線の持ち主の番号（Cloudflare が付ける）
  const lang = request.headers.get("accept-language") || "";
  const vc = visitorCookie(request);
  let trapped = false;
  let res = null;
  if (isScraper(ua)) {
    res = blockResponse(); trapped = "block";
  } else if (await checkBan(context, vc)) {
    res = blockResponse(); trapped = "block";
  } else if (request.method === "GET" || request.method === "HEAD") {
    if (isAiAgent(ua) || isAiNetwork(asn) || lacksJapanese(lang)) {
      const pathname = new URL(request.url).pathname;
      const kind = noticeKind(pathname);
      // 本物を読み込む前に返す（本物には一切触れない・処理も軽い）
      if (kind) { res = noticeResponse(kind, pathname); trapped = true; }
    }
  }
  // 人間確認の関門（2026-11-23）：上のどれにも当たらなかった相手のうち、合格の印が無い相手を止める
  // 海外からのアクセスの拒否（2026-11-23）：AIの取得役への冗談のあと、関門の前
  if (!res) {
    const geo = await geoBlock(context);
    if (geo) { res = geo; trapped = "geo"; }
  }
  if (!res) {
    const g = await gate(context);
    if (g) { res = g; trapped = "gate"; }
  }
  await recordVisit(context, vc, trapped);
  if (!res) res = await context.next();
  return withCookie(res, vc);
}
