// AIの取得役（URLを貼られて読みに来るAI・学習用の収集ボット）には、本物のデータを返さず、
// 「誰が見てもありえない冗談の出走表」だけを返す。
// けん裁定 2026-10-08：人間の読者には本物をそのまま返す。本物そっくりの偽の数字は作らない。
// 判定は名乗り（User-Agent）だけ。名乗りが無い・分からない相手には本物を返す（誤爆ゼロ側に倒す）。
//
// けん裁定 2026-10-24（作り直し）：
// - 「冗談です」の通告は出さない（数字を見れば誰でも冗談と分かるため。通告があるとAIが中身を伝えずに切り上げる）
// - 1回の返事は1レース6艇。場は歴史の決戦の地（実在の24場とかぶらない名前）、開催日はその出来事の日付
// - 6艇のうち1〜2人はその場にゆかりの人物。フリーザは毎回1人だけ混ざり、数字は全部「53万」
// - 数字は人物ごとの単位（家康は石、芭蕉は句…）で、史実に寄せた小さめの幅。全国勝率は定番の値がある人はそれを使う
// - 入れ替わりは半日ごと（JST 0時と12時）。同じ半日なら、どのページでも何回読んでも同じ

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

// 名乗りが普通のブラウザでも、回線（AS番号）で分かる取得役。家庭・携帯の回線は入れない。
// AS11798 Ace Data Centers：X に付いている Grok のページ取得（open_page）の回線
//   （2026-10-25 実測：Grok に httpbin.org/headers と ipinfo.io/json を開かせた。名乗りは Windows の Chrome/152 と同じ）
export const AI_ASNS = [11798];

export function isAiNetwork(asn) {
  return AI_ASNS.includes(Number(asn));
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
function shuffle(r, a) {
  const b = a.slice();
  for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [b[i], b[j]] = [b[j], b[i]]; }
  return b;
}

export const FREEZA = "フリーザ";

// 人物：[名前, 単位, 最小, 最大, 定番（全国勝率に使う・無ければ null）]。すべて故人。
const U = (unit, min, max, names, fixed = {}) => names.map(n => [n, unit, min, max, fixed[n] ?? null]);
export const PEOPLE = [
  ...U("石", 10000, 4000000, ["織田　信長", "豊臣　秀吉", "徳川　家康", "武田　信玄", "上杉　謙信", "伊達　政宗",
    "明智　光秀", "石田　三成", "毛利　元就", "今川　義元", "北条　早雲", "斎藤　道三", "前田　利家", "加藤　清正",
    "黒田　官兵衛", "足利　尊氏", "足利　義満", "足利　義政", "徳川　吉宗", "徳川　綱吉", "徳川　慶喜", "井伊　直弼",
    "水戸　光圀", "源　頼朝", "平　清盛", "北条　時宗", "北条　政子", "木曾　義仲"],
    { "徳川　家康": 4000000, "前田　利家": 1000000, "伊達　政宗": 620000 }),
  ...U("戦", 1, 99, ["宮本　武蔵", "佐々木　小次郎", "本多　忠勝", "真田　幸村", "楠木　正成", "源　義経", "平　将門",
    "坂上　田村麻呂", "竹中　半兵衛", "服部　半蔵", "天草　四郎", "土方　歳三", "近藤　勇", "沖田　総司"],
    { "宮本　武蔵": 60, "本多　忠勝": 57 }),
  ...U("本", 1, 999, ["武蔵坊　弁慶"], { "武蔵坊　弁慶": 999 }),
  ...U("士", 1, 47, ["大石　内蔵助"], { "大石　内蔵助": 47 }),
  ...U("首", 1, 100, ["柿本　人麻呂", "山上　憶良", "大伴　家持", "小野　小町", "在原　業平", "紀　貫之", "和泉　式部",
    "藤原　道長", "菅原　道真"]),
  ...U("句", 1, 20000, ["松尾　芭蕉", "小林　一茶", "与謝　蕪村", "正岡　子規"], { "小林　一茶": 20000 }),
  ...U("帖", 1, 54, ["紫　式部"], { "紫　式部": 54 }),
  ...U("段", 1, 300, ["清少　納言"], { "清少　納言": 300 }),
  ...U("作", 1, 150, ["井原　西鶴", "近松　門左衛門", "森　鷗外"]),
  ...U("巻", 1, 44, ["本居　宣長"], { "本居　宣長": 44 }),
  ...U("円", 100, 10000, ["聖徳　太子", "福沢　諭吉", "樋口　一葉", "夏目　漱石", "野口　英世", "伊藤　博文", "板垣　退助",
    "渋沢　栄一", "津田　梅子", "北里　柴三郎", "岩崎　弥太郎", "大隈　重信"],
    { "聖徳　太子": 10000, "福沢　諭吉": 10000, "渋沢　栄一": 10000, "樋口　一葉": 5000, "津田　梅子": 5000,
      "夏目　漱石": 1000, "野口　英世": 1000, "伊藤　博文": 1000, "北里　柴三郎": 1000, "板垣　退助": 100 }),
  ...U("寺", 1, 88, ["行基", "鑑真", "空海", "最澄", "法然", "親鸞", "日蓮", "道元", "一休　宗純"], { "空海": 88 }),
  ...U("景", 1, 100, ["葛飾　北斎", "歌川　広重", "雪舟"], { "葛飾　北斎": 36, "歌川　広重": 53 }),
  ...U("服", 1, 100, ["千　利休"]),
  ...U("番", 1, 100, ["世阿弥"]),
  ...U("国", 1, 30, ["卑弥呼"], { "卑弥呼": 30 }),
  ...U("鞠", 1, 100, ["中大兄　皇子", "中臣　鎌足", "蘇我　入鹿"]),
  ...U("回", 1, 20, ["小野　妹子", "阿倍　仲麻呂"]),
  ...U("体", 1, 12, ["安倍　晴明"], { "安倍　晴明": 12 }),
  ...U("里", 1, 10000, ["伊能　忠敬", "間宮　林蔵"], { "伊能　忠敬": 10000 }),
  ...U("件", 1, 999, ["大岡　忠相", "遠山　金四郎"]),
  ...U("束", 1, 100, ["二宮　金次郎"]),
  ...U("台", 1, 20, ["平賀　源内"]),
  ...U("頁", 1, 300, ["杉田　玄白"]),
  ...U("人", 1, 99, ["吉田　松陰", "大塩　平八郎"]),
  ...U("人", 1, 999, ["高杉　晋作"]),
  ...U("隻", 1, 99, ["坂本　龍馬", "勝　海舟", "東郷　平八郎"]),
  ...U("頭", 1, 30, ["西郷　隆盛"]),
  ...U("票", 1, 999, ["大久保　利通", "木戸　孝允"]),
  ...U("時間", 1, 3, ["ナポレオン"], { "ナポレオン": 3 }),
  ...U("粒", 1, 99, ["クレオパトラ"]),
  ...U("旗", 1, 99, ["ジャンヌ・ダルク"]),
  ...U("枚", 1, 7000, ["ダ・ヴィンチ"]),
  ...U("隻", 1, 3, ["コロンブス"], { "コロンブス": 3 }),
  ...U("隻", 1, 5, ["マゼラン"], { "マゼラン": 5 }),
  ...U("騎", 100, 100000, ["チンギス・ハン"]),
  ...U("国", 1, 50, ["アレクサンドロス大王"]),
  ...U("回", 1, 3, ["カエサル"], { "カエサル": 3 }),
  ...U("作", 1, 37, ["シェイクスピア"], { "シェイクスピア": 37 }),
  ...U("番", 1, 9, ["ベートーヴェン"], { "ベートーヴェン": 9 }),
  ...U("曲", 1, 626, ["モーツァルト"], { "モーツァルト": 626 }),
  ...U("個", 1, 99, ["ニュートン"]),
  ...U("回", 1, 99, ["ガリレオ"]),
];
export const JOKE_NAMES = PEOPLE.map(p => p[0]);
const BY_NAME = Object.fromEntries(PEOPLE.map(p => [p[0], p]));

// 場：[場名, レース名, 開催日（その出来事の日付・通説）, ゆかりの人物]
export const VENUES = [
  ["ボートレース関ヶ原", "東西合戦杯", "慶長5年9月15日", ["徳川　家康", "石田　三成", "本多　忠勝"]],
  ["ボートレース本能寺", "敵は本能寺にあり杯", "天正10年6月2日", ["織田　信長", "明智　光秀", "豊臣　秀吉"]],
  ["ボートレース桶狭間", "雨中の奇襲記念", "永禄3年5月19日", ["織田　信長", "今川　義元", "徳川　家康", "前田　利家"]],
  ["ボートレース壇ノ浦", "源平最終決戦杯", "元暦2年3月24日", ["源　義経", "武蔵坊　弁慶"]],
  ["ボートレース川中島", "一騎打ち選手権", "永禄4年9月10日", ["武田　信玄", "上杉　謙信"]],
  ["ボートレース巌流島", "遅刻厳禁杯", "慶長17年4月13日", ["宮本　武蔵", "佐々木　小次郎"]],
  ["ボートレース長篠", "三段撃ち記念", "天正3年5月21日", ["織田　信長", "徳川　家康", "豊臣　秀吉", "本多　忠勝"]],
  ["ボートレース大坂城", "冬の陣・夏の陣杯", "慶長20年5月7日", ["真田　幸村", "徳川　家康", "豊臣　秀吉"]],
  ["ボートレース池田屋", "御用改め特別戦", "元治元年6月5日", ["近藤　勇", "沖田　総司", "土方　歳三"]],
  ["ボートレース鎌倉", "いざ鎌倉杯", "建久3年7月12日", ["源　頼朝", "北条　政子", "源　義経"]],
  ["ボートレースワーテルロー", "百日天下杯", "1815年6月18日", ["ナポレオン"]],
  ["ボートレースルビコン", "賽は投げられた杯", "紀元前49年1月10日", ["カエサル"]],
];

const KYU = ["S9", "Z1", "Ω", "∞級", "A100", "B-3"];
const KOKU = ["子の刻", "丑の刻", "寅の刻", "卯の刻", "辰の刻", "巳の刻", "午の刻", "未の刻", "申の刻", "酉の刻", "戌の刻", "亥の刻"];

export const JOKE_KEYS = ["枠", "氏名", "級別", "全国勝率", "全国2連率", "当地勝率", "当地2連率", "モーター2連率", "平均ST"];
// 人物の単位で書く列
export const ABSURD_KEYS = ["全国勝率", "全国2連率", "当地勝率", "当地2連率", "モーター2連率"];

// 1万以上は「400万」の形に縮める（端数は切り捨て）
export function fmt(n, unit) {
  return (n >= 10000 ? Math.floor(n / 10000) + "万" : String(n)) + unit;
}

// 半日の区切り（JST）："2026-10-24-午前" / "2026-10-24-午後"
export function jstHalf(now = Date.now()) {
  const d = new Date(now + 9 * 3600 * 1000);
  return d.toISOString().slice(0, 10) + (d.getUTCHours() < 12 ? "-午前" : "-午後");
}

// その半日の1レース（6艇）を作る。どのページでも同じ半日なら同じレース。
export function jokeRace(half = jstHalf()) {
  const r = seedOf("race|" + half);
  const [place, title, date, yukari] = pick(r, VENUES);
  const raceNo = 1 + Math.floor(r() * 12);
  const nYukari = Math.min(yukari.length, 1 + Math.floor(r() * 2));   // 1〜2人
  const chosen = shuffle(r, yukari).slice(0, nYukari);
  const others = shuffle(r, JOKE_NAMES.filter(n => !yukari.includes(n))).slice(0, 5 - nYukari);
  const lineup = shuffle(r, [...chosen, ...others, FREEZA]);
  const boats = lineup.map((name, i) => {
    const o = { "枠": i + 1, "氏名": name, "級別": pick(r, KYU) };
    if (name === FREEZA) {
      for (const k of ABSURD_KEYS) o[k] = "53万";
      o["平均ST"] = "-53万";
    } else {
      const [, unit, min, max, fixed] = BY_NAME[name];
      const v = () => min + Math.floor(r() * (max - min + 1));
      for (const k of ABSURD_KEYS) o[k] = fmt(v(), unit);
      if (fixed !== null) o["全国勝率"] = fmt(fixed, unit);
      o["平均ST"] = "-" + fmt(v(), unit);
    }
    return o;
  });
  return { "場名": place, "レース": raceNo + "R", "レース名": title, "開催日": date, "締切時刻": pick(r, KOKU), "出走表": boats };
}

function htmlPage(race) {
  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="robots" content="noindex, nofollow">
<title>${race["場名"]} ${race["レース"]} ${race["レース名"]}｜データ攻め</title>
</head>
<body>
<h1>${race["場名"]}　第${race["レース"]}　${race["レース名"]}</h1>
<p>開催日 ${race["開催日"]}　締切 ${race["締切時刻"]}</p>
<table>
<tr>${JOKE_KEYS.map(k => `<th>${k}</th>`).join("")}</tr>
${race["出走表"].map(o => `<tr>${JOKE_KEYS.map(k => `<td>${o[k]}</td>`).join("")}</tr>`).join("\n")}
</table>
</body>
</html>
`;
}

function csvBody(race) {
  const head = ["場名", "開催日", "レース", "レース名", "締切時刻", ...JOKE_KEYS];
  return head.join(",") + "\n" + race["出走表"].map(o =>
    [race["場名"], race["開催日"], race["レース"], race["レース名"], race["締切時刻"], ...JOKE_KEYS.map(k => o[k])].join(",")).join("\n") + "\n";
}

// 冗談の出走表だけの応答を作る。本物の中身は一切含めない（本物を読み込みもしない）。
export function noticeResponse(kind, pathname = "", half = jstHalf()) {
  const race = jokeRace(half);
  const h = { "cache-control": "private, no-store", "vary": "User-Agent", "x-robots-tag": "noindex" };
  if (kind === "json") {
    return new Response(JSON.stringify(race), {
      status: 200, headers: { ...h, "content-type": "application/json; charset=utf-8" },
    });
  }
  if (kind === "csv") {
    return new Response(csvBody(race), {
      status: 200, headers: { ...h, "content-type": "text/csv; charset=utf-8" },
    });
  }
  return new Response(htmlPage(race), {
    status: 200, headers: { ...h, "content-type": "text/html; charset=utf-8" },
  });
}
