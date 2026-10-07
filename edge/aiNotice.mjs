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
// けん裁定 2026-10-08：数字は「7兆」「53万」「49億」のように単位を付けて縮めて書く。
// 選手名は本物を使わず、歴史上の人物をランダムに出す（存命の人・実在の選手は使わない）。
// 形は本物の出走表（racers_today.csv）と同じ列・12R×6人。値はURLと日付（JST）で決まる＝同じ日なら同じ値。
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

const pick = (r, a) => a[Math.floor(r() * a.length)];

// 1〜999 に 万・億・兆 のどれかを付けた文字（最小でも1万＝どの率・勝率でもありえない）。
function absurd(r) {
  return (1 + Math.floor(r() * 999)) + pick(r, ["万", "億", "兆"]);
}

export const JOKE_NAMES = [
  "織田　信長", "豊臣　秀吉", "徳川　家康", "坂本　龍馬", "西郷　隆盛", "勝　　海舟",
  "紫　　式部", "清少　納言", "聖徳　太子", "卑弥呼", "源　　義経", "武田　信玄",
  "上杉　謙信", "伊達　政宗", "宮本　武蔵", "松尾　芭蕉", "葛飾　北斎", "土方　歳三",
  "真田　幸村", "平賀　源内", "小野　妹子", "福沢　諭吉", "明智　光秀", "石田　三成",
];
const PLACES = ["月面", "マリアナ海溝", "火星第三", "クラウド", "冥王星", "電子レンジ", "AI湖"];
const KYU = ["S9", "Z1", "Ω", "∞級", "A100", "B-3"];
const SETSU = ["第∞回 AIは自分で考えよう杯", "第-1回 データ丸写し禁止杯", "第53万回 自分の目で見よう記念"];
const SEISEKI = ["99R/7/-.99/0", "0R/∞/F9/9", "13R/8/-7兆/0"];

export const JOKE_KEYS = [
  "場名", "場コード", "開催日", "レース", "枠", "登録番号", "級別", "氏名", "F数", "L数", "平均ST",
  "全国勝率", "全国2連率", "全国3連率", "当地勝率", "当地2連率", "当地3連率",
  "モーターNo", "モーター2連率", "モーター3連率", "ボートNo", "ボート2連率", "ボート3連率",
  "1日目成績", "2日目成績", "3日目成績", "4日目成績", "5日目成績", "6日目成績",
  "支部", "出身", "年齢", "締切時刻", "節名", "企画名", "日目",
];
// 単位付きの冗談の数字にする列
export const ABSURD_KEYS = [
  "登録番号", "F数", "L数", "全国勝率", "全国2連率", "全国3連率", "当地勝率", "当地2連率", "当地3連率",
  "モーターNo", "モーター2連率", "モーター3連率", "ボートNo", "ボート2連率", "ボート3連率", "年齢",
];

export function jstDay(now = Date.now()) {
  return new Date(now + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

// 12R×6人＝72行の冗談の出走表を作る。
export function jokeRows(pathname, day = jstDay()) {
  const r = seedOf(pathname + "|" + day);
  const place = pick(r, PLACES), setsu = pick(r, SETSU);
  const rows = [];
  for (let race = 1; race <= 12; race++) {
    // 1レースの6人は同じ人物が重ならないようにする
    const names = JOKE_NAMES.slice();
    for (let i = names.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [names[i], names[j]] = [names[j], names[i]]; }
    for (let w = 1; w <= 6; w++) {
      const o = {
        "場名": place, "場コード": pick(r, ["99", "-7", "00"]), "開催日": "9999-13-32",
        "レース": pick(r, ["0R", "13R", "99R", "-1R"]), "枠": pick(r, ["7", "8", "9", "0"]),
        "級別": pick(r, KYU), "氏名": names[w - 1], "平均ST": "-" + absurd(r),
      };
      for (const k of ABSURD_KEYS) o[k] = absurd(r);
      for (let d = 1; d <= 6; d++) o[d + "日目成績"] = pick(r, SEISEKI);
      o["支部"] = pick(r, PLACES); o["出身"] = pick(r, PLACES);
      o["締切時刻"] = pick(r, ["25:61", "99:99", "-3:00"]);
      o["節名"] = setsu; o["企画名"] = "予想は自分で";
      o["日目"] = pick(r, ["0日目", "99日目", "-2日目"]);
      rows.push(Object.fromEntries(JOKE_KEYS.map(k => [k, o[k]])));
    }
  }
  return rows;
}

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
${rows.map(o => `<tr>${JOKE_KEYS.map(k => `<td>${o[k]}</td>`).join("")}</tr>`).join("\n")}
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
