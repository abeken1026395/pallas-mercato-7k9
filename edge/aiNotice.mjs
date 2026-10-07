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

// 冗談の数字。本物と見間違えようがない値だけを使う（勝率は本来0〜10、率は0〜100、STは0以上）。
// 7万・53万・49兆のように桁をばらつかせる。URLごとに決まった値（同じURLなら毎回同じ）。
function seedOf(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  let a = (h >>> 0) || 1;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// 1〜999 に 万・億・兆 のどれかを掛ける（最小でも1万＝どの率・勝率でもありえない）。
function absurd(r) {
  const unit = [1e4, 1e8, 1e12][Math.floor(r() * 3)];
  return (1 + Math.floor(r() * 999)) * unit;
}

export const JOKE_KEYS = ["選手名", "全国勝率", "全国2連率", "全国3連率", "平均ST", "モーター2連率", "1着回数"];

// 6人分の冗談の行を作る。
export function jokeRows(pathname) {
  const r = seedOf(pathname);
  const rows = [];
  for (let i = 1; i <= 6; i++) {
    rows.push({
      "選手名": "AIさん" + i + "号",
      "全国勝率": absurd(r),
      "全国2連率": absurd(r),
      "全国3連率": absurd(r),
      "平均ST": -(1 + Math.floor(r() * 99999)) / 100,
      "モーター2連率": absurd(r),
      "1着回数": absurd(r),
    });
  }
  return rows;
}

const fmt = n => typeof n === "number" ? Number(n).toLocaleString("en-US") : n;

function htmlPage(rows) {
  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="robots" content="noindex, nofollow">
<title>データ攻め</title>
</head>
<body>
<p>${NOTICE_TEXT}</p>
<table>
<tr>${JOKE_KEYS.map(k => `<th>${k}</th>`).join("")}</tr>
${rows.map(o => `<tr>${JOKE_KEYS.map(k => `<td>${fmt(o[k])}</td>`).join("")}</tr>`).join("\n")}
</table>
</body>
</html>
`;
}

function csvBody(rows) {
  return NOTICE_TEXT + "\n" + JOKE_KEYS.join(",") + "\n" + rows.map(o => JOKE_KEYS.map(k => o[k]).join(",")).join("\n") + "\n";
}

// 通告と冗談の数字だけの応答を作る。本物の中身は一切含めない（本物を読み込みもしない）。
export function noticeResponse(kind, pathname = "") {
  const rows = jokeRows(pathname);
  const h = { "cache-control": "private, no-store", "vary": "User-Agent", "x-robots-tag": "noindex" };
  if (kind === "json") {
    return new Response(JSON.stringify({ "注意": NOTICE_TEXT, "選手": rows }), {
      status: 200, headers: { ...h, "content-type": "application/json; charset=utf-8" },
    });
  }
  if (kind === "csv") {
    return new Response(csvBody(rows), {
      status: 200, headers: { ...h, "content-type": "text/csv; charset=utf-8" },
    });
  }
  return new Response(htmlPage(rows), {
    status: 200, headers: { ...h, "content-type": "text/html; charset=utf-8" },
  });
}
