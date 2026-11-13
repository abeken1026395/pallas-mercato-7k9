/**
 * 24場の特性（docs/stadium/）・ファン（docs/fan/）の JSX を事前変換するビルドスクリプト。
 *
 *   正本: scripts/<ページ>/app.jsx
 *   出力: docs/<ページ>/app.js ／ docs/<ページ>/index.html の「app.js?v=」の番号
 *
 * これにより両ページから babel-standalone（cdnjs）の読み込みと画面での変換を外す。
 * React は docs/assets/ の自前版（18.2.0）を読む。cdnjs が落ちても真っ白にならない。
 * scripts/buildPlayersApp.mjs と同じ方式・同じ Babel 設定。
 *
 * 事前準備（★Babel 7系を明示すること）:
 *   npm i "@babel/core@^7.28.0" "@babel/preset-react@^7.27.0"
 * 実行:
 *   node scripts/buildPageApps.mjs            # 両ページ
 *   node scripts/buildPageApps.mjs stadium    # 1ページだけ
 *
 * app.js の1行目に正本の sha256 を書く。scripts/lintGuard.py がこれと正本を照合し、
 * 正本だけ直して変換し忘れたときに FAIL にする。
 *
 * Babel 設定は変更しないこと:
 *   runtime: "classic"  … automatic にすると import 文が生成され UMD 構成で動かない
 *   sourceType: "script" … module にすると "use strict" が付き
 *                          トップレベルの変数がグローバルでなくなる
 */
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import babel from "@babel/core";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const PAGES = ["stadium", "fan"];
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");

const want = process.argv.slice(2);
for (const p of want.length ? want : PAGES) {
  if (!PAGES.includes(p)) throw new Error("知らないページ: " + p);
  const SRC = join(ROOT, "scripts", p, "app.jsx");
  const OUT = join(ROOT, "docs", p, "app.js");
  const HTML = join(ROOT, "docs", p, "index.html");
  const src = readFileSync(SRC, "utf8");
  const result = babel.transformSync(src, {
    filename: SRC,
    presets: [["@babel/preset-react", { runtime: "classic" }]],
    sourceType: "script",
    compact: false,
    babelrc: false,
    configFile: false,
  });
  if (!result || typeof result.code !== "string") {
    throw new Error("Babel の変換結果が空です: " + SRC);
  }
  // 照合用の sha256 は改行を LF にそろえて取る（Windows の作業ツリーは CRLF のことがある。lintGuard も LF で読む）
  const banner = "// 自動生成ファイル。手で編集しないこと。正本は scripts/" + p + "/app.jsx sha256=" + sha(src.replace(/\r\n/g, "\n"));
  const out = banner + "\n" + result.code + "\n";
  writeFileSync(OUT, out, "utf8");
  const v = sha(out).slice(0, 8);
  const html = readFileSync(HTML, "utf8");
  const re = /<script src="app\.js\?v=[0-9a-f]{8}" defer><\/script>/g;
  const hits = html.match(re) || [];
  if (hits.length !== 1) throw new Error("index.html の app.js 読み込みが1か所でない: " + HTML + " " + hits.length);
  const html2 = html.replace(re, '<script src="app.js?v=' + v + '" defer></script>');
  if (html2 !== html) writeFileSync(HTML, html2, "utf8");
  console.log("wrote", OUT, Buffer.byteLength(out, "utf8"), "bytes ／ v=" + v);
}
