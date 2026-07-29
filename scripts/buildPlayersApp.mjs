/**
 * 選手図鑑（docs/players/）の JSX を事前変換するビルドスクリプト。
 *
 *   正本: scripts/players/app.jsx
 *   出力: docs/players/app.js
 *
 * これにより docs/players/index.html から babel-standalone（CDN・gzip 約 584KB）の
 * 読み込みと実行時トランスパイルを外せる。
 *
 * 事前準備:
 *   npm i @babel/core @babel/preset-react
 * 実行:
 *   node scripts/buildPlayersApp.mjs
 *
 * Babel 設定は変更しないこと:
 *   runtime: "classic"  … automatic にすると import 文が生成され UMD 構成で動かない
 *   sourceType: "script" … module にすると "use strict" が付き
 *                          トップレベルの変数がグローバルでなくなる
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import babel from "@babel/core";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const SRC = join(ROOT, "scripts", "players", "app.jsx");
const OUT = join(ROOT, "docs", "players", "app.js");
const BANNER = "// 自動生成ファイル。手で編集しないこと。正本は scripts/players/app.jsx";

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

const out = BANNER + "\n" + result.code + "\n";
writeFileSync(OUT, out, "utf8");
console.log("wrote", OUT, Buffer.byteLength(out, "utf8"), "bytes");
