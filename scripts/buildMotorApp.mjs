/**
 * モーター成績ビューワー（docs/motor/）の JSX を事前変換するビルドスクリプト。
 *
 *   正本: scripts/motor/app.jsx
 *   出力: docs/motor/app.js
 *
 * これにより docs/motor/index.html から babel-standalone（CDN）の読み込みと
 * 実行時トランスパイル（125KB の JSX を iPhone 上で毎回コンパイル）を外せる。
 * scripts/buildPlayersApp.mjs と同じ方式・同じ Babel 設定。
 *
 * 事前準備（★Babel 7系を明示すること）:
 *   npm i "@babel/core@^7.28.0" "@babel/preset-react@^7.27.0"
 *
 *   無指定の `npm i @babel/core` は Babel 8 を入れる。Babel 8 は ESM 化で
 *   default export を持たないため、下の `import babel from "@babel/core"` が
 *   「does not provide an export named 'default'」で失敗する。
 * 実行:
 *   node scripts/buildMotorApp.mjs
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
const SRC = join(ROOT, "scripts", "motor", "app.jsx");
const OUT = join(ROOT, "docs", "motor", "app.js");
const BANNER = "// 自動生成ファイル。手で編集しないこと。正本は scripts/motor/app.jsx";

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
