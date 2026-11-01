// node --test edge/aiNotice.test.mjs
// AIの取得役には冗談の出走表だけ、人間には本物がそのまま出ることを確かめる。
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../functions/_middleware.js";
import { FREEZA, PEOPLE, JOKE_NAMES, VENUES, JOKE_KEYS, ABSURD_KEYS, jokeRace, jstHalf, fmt, noticeKind } from "./aiNotice.mjs";

const BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const REAL = "本物の中身 全国勝率 6.12";

const JA = "ja-JP,ja;q=0.9";
async function get(path, ua, asn, lang = JA) {
  let touched = false;
  const headers = { "user-agent": ua };
  if (lang !== null) headers["accept-language"] = lang;
  const request = new Request("https://example.pages.dev" + path, { headers });
  if (asn !== undefined) Object.defineProperty(request, "cf", { value: { asn } });
  const res = await onRequest({ request, next: async () => { touched = true; return new Response(REAL, { status: 200 }); } });
  return { status: res.status, type: res.headers.get("content-type") || "", text: await res.text(), touched };
}

const TARGETS = [
  "/racers/", "/racers/index.html", "/racers/racers_today.csv",
  "/players/card.html", "/players/card/common.json", "/players/card/p/0.json", "/players/card/h2h/0.json",
  "/highlights/", "/highlights/highlights.json", "/highlights/racerStatsToday.json",
  "/data/kansenki/articles/20260709-01.json", "/data/tenjiStats.json",
  "/motor/", "/motor/motors_all.csv", "/motor-maintenance/",
  "/next/ichimark.html", "/next/ichimark", "/next/ichimark/mae_20261031.json", "/next/ichimark/maeIndex.json",
];
const OUTSIDE = ["/", "/results/", "/kensho/", "/data/weather.json", "/data/verify_summary.json", "/stadium/", "/robots.txt"];
const AI = ["ChatGPT-User/1.0", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +Claude-User@anthropic.com)", "Perplexity-User/1.0", "GPTBot/1.1", "ClaudeBot/1.0", "CCBot/2.0"];

// 2026-10-08 午前から半日ずつ 60 区切り（30日分）
const HALVES = Array.from({ length: 60 }, (_, i) => jstHalf(Date.UTC(2026, 9, 7, 15) + i * 12 * 3600000));
const BOAT_NAMES = new Set([...JOKE_NAMES, FREEZA]);

test("AIの名乗り × 対象：本物に触れず、冗談の出走表だけ（通告の文は無い）", async () => {
  const race = jokeRace();
  for (const ua of AI) for (const p of TARGETS) {
    const a = await get(p, ua);
    assert.equal(a.status, 200, p);
    assert.equal(a.touched, false, `${p} で本物を読み込んだ`);
    assert.ok(!a.text.includes(REAL), `${p} に本物が混ざった`);
    assert.ok(a.text.includes(race["場名"]) && a.text.includes(FREEZA), `${p} に冗談の出走表が無い`);
    assert.ok(!a.text.includes("冗談"), `${p} に通告の文が残っている`);
    assert.ok(a.text.length < 20000, `${p} の返事が大きすぎる`);
  }
});

test("返す形：JSONは場名とレースと6艇、CSVは見出し＋6行、HTMLは見出しに場名・レース・レース名", async () => {
  const j = JSON.parse((await get("/players/card/p/0.json", "ChatGPT-User/1.0")).text);
  assert.equal(j["出走表"].length, 6);
  assert.match(j["レース"], /^([1-9]|1[0-2])R$/);
  const jt = await get("/players/card/p/0.json", "ChatGPT-User/1.0");
  assert.match(jt.type, /application\/json; charset=utf-8/);
  const c = (await get("/racers/racers_today.csv", "ChatGPT-User/1.0")).text.trim().split("\n");
  assert.equal(c.length, 7);
  assert.ok(c[0].startsWith("場名,開催日,レース,レース名,締切時刻,枠,氏名"));
  const h = (await get("/racers/", "ChatGPT-User/1.0")).text;
  assert.match(h, /<h1>ボートレース.+　第([1-9]|1[0-2])R　.+<\/h1>/);
});

test("人物は126人・重複なし・全員に単位と幅があり、定番の値は幅の中", () => {
  assert.equal(PEOPLE.length, 126);
  assert.equal(new Set(JOKE_NAMES).size, 126);
  for (const [n, unit, min, max, fixed] of PEOPLE) {
    assert.ok(unit && min >= 1 && max >= min, n);
    if (fixed !== null) assert.ok(fixed >= min && fixed <= max, `${n} の定番 ${fixed} が幅の外`);
  }
  for (const n of ["始皇帝", "諸葛　孔明", "劉　備", "曹　操", "孫　子", "孔子"]) assert.ok(!JOKE_NAMES.includes(n), n);
});

test("場は12・ゆかりの人物はみな名簿にいる", () => {
  assert.equal(VENUES.length, 12);
  for (const [place, , , yukari] of VENUES) {
    assert.ok(place.startsWith("ボートレース"), place);
    for (const n of yukari) assert.ok(JOKE_NAMES.includes(n), `${place} の ${n}`);
  }
});

test("1レース：6艇・枠1〜6・重複なし・フリーザは1人だけで全部53万・ゆかりは1〜2人・数字は人物の単位", () => {
  for (const half of HALVES) {
    const race = jokeRace(half);
    const boats = race["出走表"];
    assert.equal(boats.length, 6, half);
    assert.deepEqual(boats.map(o => o["枠"]), [1, 2, 3, 4, 5, 6]);
    for (const o of boats) assert.deepEqual(Object.keys(o).sort(), JOKE_KEYS.slice().sort());
    assert.equal(new Set(boats.map(o => o["氏名"])).size, 6, half);
    for (const o of boats) assert.ok(BOAT_NAMES.has(o["氏名"]), o["氏名"]);
    const fz = boats.filter(o => o["氏名"] === FREEZA);
    assert.equal(fz.length, 1, half);
    for (const k of ABSURD_KEYS) assert.equal(fz[0][k], "53万");
    assert.equal(fz[0]["平均ST"], "-53万");
    const v = VENUES.find(x => x[0] === race["場名"]);
    assert.ok(v, race["場名"]);
    assert.equal(race["開催日"], v[2]);
    const ny = boats.filter(o => v[3].includes(o["氏名"])).length;
    assert.ok(ny >= 1 && ny <= 2, `${half} ゆかり ${ny}人`);
    for (const o of boats) {
      if (o["氏名"] === FREEZA) continue;
      const [, unit, min, max, fixed] = PEOPLE.find(p => p[0] === o["氏名"]);
      for (const k of ABSURD_KEYS) assert.ok(o[k].endsWith(unit), `${o["氏名"]} ${k}=${o[k]}`);
      assert.ok(o["平均ST"].startsWith("-") && o["平均ST"].endsWith(unit));
      if (fixed !== null) assert.equal(o["全国勝率"], fmt(fixed, unit));
      for (const k of ABSURD_KEYS) assert.ok(!/^-?[0-9]+(\.[0-9]+)?$/.test(o[k]), "素の数字");
    }
  }
});

test("半日ごとに入れ替わる・同じ半日なら同じ・30日で12場がすべて出る", () => {
  assert.equal(jstHalf(Date.UTC(2026, 9, 23, 15, 0)), "2026-10-24-午前");   // JST 0:00
  assert.equal(jstHalf(Date.UTC(2026, 9, 24, 2, 59)), "2026-10-24-午前");   // JST 11:59
  assert.equal(jstHalf(Date.UTC(2026, 9, 24, 3, 0)), "2026-10-24-午後");    // JST 12:00
  assert.deepEqual(jokeRace(HALVES[0]), jokeRace(HALVES[0]));
  let changed = 0;
  for (let i = 1; i < HALVES.length; i++) if (JSON.stringify(jokeRace(HALVES[i])) !== JSON.stringify(jokeRace(HALVES[i - 1]))) changed++;
  assert.equal(changed, HALVES.length - 1);
  const places = new Set(HALVES.map(h => jokeRace(h)["場名"]));
  assert.ok(places.size >= 10, `30日で出た場 ${places.size}`);
});

test("数字の書き方：1万以上は「400万」の形", () => {
  assert.equal(fmt(4000000, "石"), "400万石");
  assert.equal(fmt(620000, "石"), "62万石");
  assert.equal(fmt(54, "帖"), "54帖");
  assert.equal(fmt(10000, "円"), "1万円");
});

test("人間（普通のブラウザ）× 対象：本物がそのまま", async () => {
  for (const p of TARGETS) {
    const a = await get(p, BROWSER);
    assert.equal(a.touched, true);
    assert.equal(a.text, REAL, p);
  }
});

test("回線：Grok の回線（AS11798）は普通のブラウザの名乗りでも冗談、ほかの回線は本物", async () => {
  const GROK_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36";
  for (const p of TARGETS) {
    const a = await get(p, GROK_UA, 11798);
    assert.equal(a.touched, false, `${p} で本物を読み込んだ`);
    assert.ok(a.text.includes(FREEZA), p);
  }
  for (const asn of [2516, 17676, 4713, 13335, 15169, 0]) {   // KDDI・ソフトバンク・NTT・Cloudflare（プライベートリレー）・Google・不明
    assert.equal((await get("/racers/", GROK_UA, asn)).text, REAL, `AS${asn}`);
  }
  for (const p of OUTSIDE) assert.equal((await get(p, GROK_UA, 11798)).text, REAL, p);
});

test("言語の設定：日本語が無い・送らない相手は冗談、日本語があれば本物（Grok 型）", async () => {
  const GROK_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36";
  for (const p of TARGETS) {
    for (const lang of ["en-US,en;q=0.9", "zh-CN,zh;q=0.9", null]) {
      const a = await get(p, GROK_UA, 9009, lang);
      assert.equal(a.touched, false, `${p} ${lang}`);
      assert.ok(a.text.includes(FREEZA), `${p} ${lang}`);
    }
  }
  for (const lang of ["ja-JP,ja;q=0.9", "ja", "en-US,en;q=0.9,ja;q=0.8", "ja-JP,en-US;q=0.9"]) {
    assert.equal((await get("/racers/", GROK_UA, 2516, lang)).text, REAL, lang);
  }
  for (const p of OUTSIDE) assert.equal((await get(p, GROK_UA, 9009, "en-US,en;q=0.9")).text, REAL, p);
});

test("名乗りが空：本物がそのまま（誤爆ゼロ側）", async () => {
  for (const p of TARGETS) assert.equal((await get(p, "")).text, REAL, p);
});

test("AIの名乗り × 対象外：本物がそのまま", async () => {
  for (const p of OUTSIDE) assert.equal((await get(p, "ChatGPT-User/1.0")).text, REAL, p);
});

test("対象判定", () => {
  assert.equal(noticeKind("/racers/"), "html");
  assert.equal(noticeKind("/highlights/highlights.json"), "json");
  assert.equal(noticeKind("/motor/motors_all.csv"), "csv");
  assert.equal(noticeKind("/results/"), null);
});
