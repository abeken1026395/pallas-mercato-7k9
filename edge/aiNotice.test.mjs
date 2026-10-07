// node --test edge/aiNotice.test.mjs
// AIの取得役には通告と冗談の数字だけ、人間には本物がそのまま出ることを確かめる。
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../functions/_middleware.js";
import { NOTICE_TEXT, jokeRows, noticeKind, ABSURD_KEYS, JOKE_KEYS, JOKE_NAMES } from "./aiNotice.mjs";

const BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const REAL = "本物の中身 全国勝率 6.12";

async function get(path, ua) {
  let touched = false;
  const request = new Request("https://datazeme.pages.dev" + path, { headers: { "user-agent": ua } });
  const res = await onRequest({ request, next: async () => { touched = true; return new Response(REAL, { status: 200 }); } });
  return { status: res.status, type: res.headers.get("content-type") || "", text: await res.text(), touched };
}

const TARGETS = [
  "/racers/", "/racers/index.html", "/racers/racers_today.csv",
  "/players/card.html", "/players/card/common.json", "/players/card/p/0.json", "/players/card/h2h/0.json",
  "/highlights/", "/highlights/highlights.json", "/highlights/racerStatsToday.json",
  "/data/kansenki/articles/20260709-01.json", "/data/tenjiStats.json",
  "/motor/", "/motor/motors_all.csv", "/motor-maintenance/",
];
const OUTSIDE = ["/", "/results/", "/kensho/", "/data/weather.json", "/data/verify_summary.json", "/stadium/", "/robots.txt"];
const AI = ["ChatGPT-User/1.0", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +Claude-User@anthropic.com)", "Perplexity-User/1.0", "GPTBot/1.1", "ClaudeBot/1.0", "CCBot/2.0"];

test("AIの名乗り × 対象：本物に触れず、通告と冗談の数字だけ", async () => {
  for (const ua of AI) for (const p of TARGETS) {
    const a = await get(p, ua);
    assert.equal(a.status, 200, p);
    assert.equal(a.touched, false, `${p} で本物を読み込んだ`);
    assert.ok(a.text.includes(NOTICE_TEXT), `${p} に通告が無い`);
    assert.ok(!a.text.includes("6.12"), `${p} に本物が混ざった`);
    assert.ok(a.text.length < 60000, `${p} の返事が大きすぎる`);
  }
});

test("返す形：JSONは JSON、CSVは1行目が通告、HTMLは本文の先頭が通告", async () => {
  const j = await get("/players/card/p/0.json", "ChatGPT-User/1.0");
  const o = JSON.parse(j.text);
  assert.equal(Object.keys(o)[0], "注意");
  assert.equal(o["選手"].length, 72);
  assert.match(j.type, /application\/json; charset=utf-8/);
  const c = await get("/racers/racers_today.csv", "ChatGPT-User/1.0");
  assert.equal(c.text.split("\n")[0], NOTICE_TEXT);
  const h = await get("/racers/", "ChatGPT-User/1.0");
  assert.ok(h.text.indexOf(NOTICE_TEXT) < h.text.indexOf("<table>"));
});

test("冗談の数字は「7兆」「53万」の形・桁がばらつく・名前は歴史上の人物・URLと日付で決まる", () => {
  const units = new Set();
  const D = "2026-10-08";
  for (const p of TARGETS) {
    const rows = jokeRows(p, D);
    assert.equal(rows.length, 72);
    assert.deepEqual(rows, jokeRows(p, D), `${p} が同じ日なのに違う`);
    for (const o of rows) {
      assert.deepEqual(Object.keys(o), JOKE_KEYS);
      assert.ok(JOKE_NAMES.includes(o["氏名"]), o["氏名"]);
      for (const k of ABSURD_KEYS) {
        assert.match(o[k], /^[1-9][0-9]{0,2}(万|億|兆)$/, `${k}=${o[k]}`);  // 最小でも1万。0の並びは出さない
        units.add(o[k].slice(-1));
      }
      assert.match(o["平均ST"], /^-[1-9][0-9]{0,2}(万|億|兆)$/);   // STは負にならない
    }
  }
  for (let i = 0; i < 72; i += 6) {
    assert.equal(new Set(jokeRows("/racers/", D).slice(i, i + 6).map(o => o["氏名"])).size, 6, "1レースに同じ人物");
  }
  assert.equal(units.size, 3, "万・億・兆がそろっていない");
  assert.notDeepEqual(jokeRows("/racers/", D), jokeRows("/motor/", D));
  assert.notDeepEqual(jokeRows("/racers/", D), jokeRows("/racers/", "2026-10-09"), "日替わりになっていない");
});

test("人間（普通のブラウザ）× 対象：本物がそのまま", async () => {
  for (const p of TARGETS) {
    const a = await get(p, BROWSER);
    assert.equal(a.touched, true);
    assert.equal(a.text, REAL, p);
  }
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
