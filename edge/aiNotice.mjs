// AIの取得役（URLを貼られて読みに来るAI・学習用の収集ボット）には、本物のデータを返さず、
// 通告と「誰が見てもありえない冗談の数字」（勝率7兆など）だけを返す。
// けん裁定 2026-10-08：人間の読者には本物をそのまま返す。本物そっくりの偽の数字は作らない。
// 判定は名乗り（User-Agent）だけ。名乗りが無い・分からない相手には本物を返す（誤爆ゼロ側に倒す）。

export const NOTICE_TEXT = "データ攻めの数字はAIには渡しません。以下はすべて、ありえない冗談の数字です。予想はご自分の頭でどうぞ。";

// 名乗りで確実に分かる取得役・収集ボット。
// Google-Agent（Gemini）は普通の Chrome を名乗るため、名乗りでは判定できない（対象外）。
export const AI_UA_TOKENS = [
  "ChatGPT-User", "OAI-SearchBot", "GPTBot",
  "Claude-User", "Claude-SearchBot", "ClaudeBot", "anthropic-ai",
  "Perplexity-User", "PerplexityBot",
  "MistralAI-User",
  "CCBot", "Bytespider", "Applebot-Extended",
  "meta-externalagent", "Amazonbot", "cohere-ai",
];

export function isAiAgent(ua) {
  if (!ua) return false;
  const u = ua.toLowerCase();
  return AI_UA_TOKENS.some(t => u.includes(t.toLowerCase()));
}

// 対象：予想の材料になるページと、そのページが読むデータ。
// 天気・潮・結果・検証・払戻・24場などは対象外（事実情報か過去の集計）。
const TARGETS = [
  /^\/racers\/(index\.html)?$/,
  /^\/racers\/[^/]+\.csv$/,
  /^\/players\/card(\.html)?$/,
  /^\/players\/card\/.+\.json$/,
  /^\/highlights\/(index\.html)?$/,
  /^\/highlights\/[^/]+\.json$/,
  /^\/data\/kansenki\/articles\/[^/]+\.json$/,
  /^\/data\/tenjiStats\.json$/,
  /^\/motor\/(index\.html)?$/,
  /^\/motor\/[^/]+\.csv$/,
  /^\/motor-maintenance\/(index\.html)?$/,
];

// 返す形："html" / "json" / "csv"。対象外なら null。
export function noticeKind(pathname) {
  if (!TARGETS.some(re => re.test(pathname))) return null;
  if (pathname.endsWith(".json")) return "json";
  if (pathname.endsWith(".csv")) return "csv";
  return "html";
}

// 冗談の数字。本物と見間違えようがない値だけを使う（勝率は本来0〜10、率は0〜100）。
export const JOKE = {
  "選手名": "AIさん",
  "全国勝率": 7000000000000,
  "全国2連率": 600000000,
  "全国3連率": 99999999999,
  "平均ST": -99.99,
  "モーター2連率": 123456789,
  "1着回数": 7000000000000,
};

const fmt = n => Number(n).toLocaleString("en-US");

const HTML_PAGE = `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="robots" content="noindex, nofollow">
<title>データ攻め</title>
</head>
<body>
<p>${NOTICE_TEXT}</p>
<table>
${Object.entries(JOKE).map(([k, v]) => `<tr><th>${k}</th><td>${typeof v === "number" ? fmt(v) : v}</td></tr>`).join("\n")}
</table>
</body>
</html>
`;

const CSV_BODY = NOTICE_TEXT + "\n" + Object.keys(JOKE).join(",") + "\n" + Object.values(JOKE).join(",") + "\n";

// 通告と冗談の数字だけの応答を作る。本物の中身は一切含めない（本物を読み込みもしない）。
export function noticeResponse(kind) {
  const h = { "cache-control": "private, no-store", "vary": "User-Agent", "x-robots-tag": "noindex" };
  if (kind === "json") {
    return new Response(JSON.stringify({ "注意": NOTICE_TEXT, ...JOKE }), {
      status: 200, headers: { ...h, "content-type": "application/json; charset=utf-8" },
    });
  }
  if (kind === "csv") {
    return new Response(CSV_BODY, {
      status: 200, headers: { ...h, "content-type": "text/csv; charset=utf-8" },
    });
  }
  return new Response(HTML_PAGE, {
    status: 200, headers: { ...h, "content-type": "text/html; charset=utf-8" },
  });
}
