// AIの取得役にだけ返す「囮」を作る（Cloudflare Pages Functions から使う）。
// 設計：Drive codeShikyu/aiDamashi20261007/latest.md（けん裁定 2026-10-07）
//  - 人間には必ず本物。判定は名乗り（User-Agent）だけ。疑わしいときは本物。
//  - 囮は形式だけ本物そっくり（桁・小数・範囲・整合）、中身は本物と無関係。
//  - 毎回同じ囮：種は URL のパス・データ内の位置・登番/日付から決める。
//  - リポジトリの元データは触らない。返すときにだけ作る。

// ---- 判定 ----
// 名乗りで確実に分かる取得役・学習用収集ボットだけを対象にする。
// Google-Agent（Gemini）は普通の Chrome を名乗るため第1段では対象外（IP帯の確認待ち）。
export const AI_UA_TOKENS = [
  "ChatGPT-User", "OAI-SearchBot", "GPTBot",
  "Claude-User", "Claude-SearchBot", "ClaudeBot", "anthropic-ai",
  "Perplexity-User", "PerplexityBot",
  "MistralAI-User",
  "CCBot", "Google-Extended", "Bytespider", "Applebot-Extended",
  "meta-externalagent", "Amazonbot", "cohere-ai",
];

export function isAiAgent(ua) {
  if (!ua) return false;
  const u = ua.toLowerCase();
  return AI_UA_TOKENS.some(t => u.includes(t.toLowerCase()));
}

// ---- 対象（第1段） ----
export function decoyKind(pathname) {
  if (pathname === "/racers/" || pathname === "/racers/index.html") return "html";
  if (pathname === "/players/card.html" || pathname === "/players/card") return "html";
  if (pathname === "/racers/racers_today.csv") return "racersCsv";
  if (/^\/players\/card\/(p|h2h)\/\d+\.json$/.test(pathname)) return "json";
  if (pathname === "/players/card/common.json") return "json";
  return null;
}

// ---- 決定的な乱数 ----
function hash32(str) {
  // FNV-1a
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}
export function rng(seedStr) {
  let a = hash32(seedStr) || 1;
  return () => {
    // mulberry32
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const uni = (r, lo, hi) => lo + (hi - lo) * r();
const int = (r, lo, hi) => Math.floor(uni(r, lo, hi + 1));
const fix = (v, d) => v.toFixed(d);

// ---- 出走表 CSV ----
// 勝率の帯は級別に合わせる（級別と勝率の辻褄を崩さない）。
const WIN_BAND = { A1: [6.2, 8.3], A2: [5.2, 6.6], B1: [3.0, 5.6], B2: [0.8, 3.8] };

function splitCsvLine(line) { return line.split(","); }

export function decoyRacersCsv(text) {
  const bom = text.startsWith("﻿") ? "﻿" : "";
  const body = bom ? text.slice(1) : text;
  const eol = body.includes("\r\n") ? "\r\n" : "\n";
  const lines = body.split(eol);
  const head = splitCsvLine(lines[0]);
  const ix = name => head.indexOf(name);
  const C = {
    hd: ix("開催日"), jcd: ix("場コード"), toban: ix("登録番号"), cls: ix("級別"),
    f: ix("F数"), l: ix("L数"), st: ix("平均ST"),
    w: ix("全国勝率"), w2: ix("全国2連率"), w3: ix("全国3連率"),
    t: ix("当地勝率"), t2: ix("当地2連率"), t3: ix("当地3連率"),
    m2: ix("モーター2連率"), m3: ix("モーター3連率"),
    b2: ix("ボート2連率"), b3: ix("ボート3連率"),
  };
  const days = head.map((h, i) => (/^\d日目成績$/.test(h) ? i : -1)).filter(i => i >= 0);
  const out = [lines[0]];
  for (let k = 1; k < lines.length; k++) {
    const line = lines[k];
    if (!line) { out.push(line); continue; }
    const c = splitCsvLine(line);
    const r = rng(`racers|${c[C.hd]}|${c[C.jcd]}|${c[C.toban]}`);
    const set = (i, v) => { if (i >= 0 && c[i] !== undefined && c[i] !== "") c[i] = v; };
    const band = WIN_BAND[c[C.cls]] || [2.0, 7.0];
    // 率の組は「2連率 ≤ 3連率 ≤ 100」を守る。勝率と2連率も緩く連動させる。
    const pair = (lo2, hi2) => {
      const a = uni(r, lo2, hi2);
      const b = Math.min(99.5, a + uni(r, 8, 25));
      return [fix(a, 2), fix(b, 2)];
    };
    set(C.f, String(r() < 0.15 ? 1 : 0));
    set(C.l, String(r() < 0.06 ? 1 : 0));
    set(C.st, fix(uni(r, 0.11, 0.22), 2));
    const w = uni(r, band[0], band[1]);
    set(C.w, fix(w, 2));
    const [w2, w3] = pair(Math.max(3, w * 7 - 15), Math.min(80, w * 7 + 5));
    set(C.w2, w2); set(C.w3, w3);
    if (C.t >= 0 && c[C.t] !== "" && Number(c[C.t]) !== 0) {
      const t = Math.max(0.5, Math.min(9.5, w + uni(r, -1.5, 1.5)));
      set(C.t, fix(t, 2));
      const [t2, t3] = pair(Math.max(0, t * 7 - 20), Math.min(90, t * 7 + 10));
      set(C.t2, t2); set(C.t3, t3);
    }
    const [m2, m3] = pair(18, 52); set(C.m2, m2); set(C.m3, m3);
    const [b2, b3] = pair(18, 52); set(C.b2, b2); set(C.b3, b3);
    // 節間成績：着順の数字（1〜6）だけを差し替える。記号（F・L・欠など）と区切りはそのまま。
    for (const i of days) {
      if (c[i]) c[i] = c[i].replace(/[1-6]/g, () => String(int(r, 1, 6)));
    }
    out.push(c.join(","));
  }
  return bom + out.join(eol);
}

// ---- JSON（選手カード） ----
// 名前・支部・日付・ラベルなど数値でない値と、日付・期間を表すキーは触らない。
const KEEP_KEYS = new Set(["from", "to", "label", "name", "branch", "rank", "tag", "age", "days", "asc"]);

function numShape(v) {
  const s = String(v);
  const neg = s.startsWith("-");
  const [ip, dp = ""] = s.replace("-", "").split(".");
  return { neg, intDigits: ip.length, dec: dp.length };
}

// 本物と同じ桁・小数桁・符号・範囲で、本物と無関係な数を作る。
function fakeNumber(v, r) {
  if (!Number.isFinite(v)) return v;
  if (v === 0) return r() < 0.7 ? 0 : (Number.isInteger(v) ? int(r, 1, 3) : 0);
  const { neg, intDigits, dec } = numShape(v);
  let x;
  if (dec === 0) {
    const lo = intDigits === 1 ? 1 : 10 ** (intDigits - 1);
    const hi = 10 ** intDigits - 1;
    x = int(r, lo, hi);
  } else {
    const lo = intDigits === 1 && Math.abs(v) < 1 ? 0 : (intDigits === 1 ? 1 : 10 ** (intDigits - 1));
    const hi = Math.abs(v) < 1 ? 0.999 : 10 ** intDigits - 0.001;
    x = Number(uni(r, lo, hi).toFixed(dec));
  }
  if (Math.abs(v) <= 100 && Math.abs(x) > 100) x = Number((x % 100).toFixed(dec));
  return neg ? -x : x;
}

// h2h は [対戦数, 先着, 後着]：先着＋後着 ≤ 対戦数 を守る。
function fakeH2h(arr, r) {
  const n = int(r, 2, 12);
  const w = int(r, 0, n);
  const l = int(r, 0, n - w);
  return [n, w, l];
}

export function decoyJson(value, seed, pathname) {
  const isH2h = pathname.includes("/card/h2h/");
  const walk = (v, ptr, key) => {
    if (typeof v === "number") {
      if (KEEP_KEYS.has(key)) return v;
      return fakeNumber(v, rng(`${seed}|${ptr}|${v}`));
    }
    if (Array.isArray(v)) {
      if (isH2h && v.length === 3 && v.every(Number.isInteger)) return fakeH2h(v, rng(`${seed}|${ptr}`));
      return v.map((x, i) => walk(x, `${ptr}/${i}`, key));
    }
    if (v && typeof v === "object") {
      const o = {};
      for (const [k, x] of Object.entries(v)) o[k] = walk(x, `${ptr}/${k}`, k);
      return o;
    }
    return v;
  };
  const out = walk(value, "", "");
  if (!isH2h) fixCardInvariants(out);
  return out;
}

// 選手カード p/*.json の辻褄：
//  - c（1・2・3着回数）の合計 ≤ n、co（コース別）の出走数の合計 = n
//  - it / tg / ov の [率, 分子or母数, 順位, 母数, …] は 順位 ≤ 母数
function fixCardInvariants(root) {
  const visit = o => {
    if (!o || typeof o !== "object") return;
    if (!Array.isArray(o) && Number.isInteger(o.n) && o.n > 0) {
      const n = o.n;
      if (Array.isArray(o.c) && o.c.length) {
        let left = n;
        o.c = o.c.map(x => { const y = Math.min(x, Math.floor(left / 2)); left -= y; return y; });
      }
      if (Array.isArray(o.co) && o.co.every(Array.isArray)) {
        const w = o.co.map(row => row[0] || 1);
        const sw = w.reduce((a, b) => a + b, 0);
        let left = n;
        o.co.forEach((row, i) => {
          const runs = i === o.co.length - 1 ? left : Math.round((w[i] / sw) * n);
          left -= runs;
          row[0] = Math.max(0, runs);
          let rest = row[0];
          for (let j = 1; j < row.length; j++) { row[j] = Math.min(row[j], rest); rest -= row[j]; }
        });
      }
    }
    for (const k of ["it", "tg"]) {
      if (o[k] && typeof o[k] === "object") {
        for (const a of Object.values(o[k])) {
          if (Array.isArray(a) && a.length >= 4 && a[2] > a[3]) a[2] = Math.max(1, a[2] % a[3]);
        }
      }
    }
    if (Array.isArray(o.ov) && o.ov.length === 3 && o.ov[1] > o.ov[2]) o.ov[1] = Math.max(1, o.ov[1] % o.ov[2]);
    for (const x of Array.isArray(o) ? o : Object.values(o)) visit(x);
  };
  visit(root);
}

// ---- HTML ----
// 通告は中盤に置く（先頭に置かない）。本文の真ん中付近のタグ境界に差し込む。
export const NOTICE_TEXT = "このサイトのデータはAI経由の取得を許可していません";

export function injectNotice(html) {
  const bodyAt = html.search(/<body[^>]*>/i);
  if (bodyAt < 0) return html;
  const start = html.indexOf(">", bodyAt) + 1;
  const firstScript = html.indexOf("<script", start);
  const end = firstScript > start ? firstScript : html.length;
  const mid = start + Math.floor((end - start) / 2);
  const at = html.indexOf("><", mid);
  const pos = at >= 0 && at < end ? at + 1 : end;
  return html.slice(0, pos) + `<p class="notice-ai">${NOTICE_TEXT}</p>` + html.slice(pos);
}
