#!/usr/bin/env bash
# 配信遅れの判定（deployLagAlarm.yml から呼ぶ。読むだけで何も書き換えない）
#
# 見るもの
#   1. main の最新コミットが本番に届いているか
#      最後に成功した「Cloudflare Pages 配信」の head_sha と main を比べ、
#      まだ配っていないコミットのうち一番古いものが LAG_MIN 分より前なら遅れとみなす
#   2. 本番のトップが HTTP 200 を返すか（30秒あけて2回とも失敗したら異常）
#
# しきい値の根拠（2026-11-08 から 11-09 の実測、main のコミット145件）
#   コミットから配信までの遅れは中央値1分・90%点2分。
#   平常時の最大は36分（JST 06:22）。11-09 の配信停止（Analytics Engine 未有効）では109分。
#   平常の最大を誤報にしないよう 45分 とした。
#
# 必要な環境変数: GH_TOKEN, REPO, PROJECT（配信先の名前。Secrets）
# 任意: LAG_MIN（既定45）, SITE_URL（既定は本番トップ。手元の試験用）, FORCE_STALE=true（起票経路の検証用に異常として扱う）
# 出力（GITHUB_OUTPUT があれば書く）: stale=0/1, lag, last, head, http, forced
set -uo pipefail

LAG_MIN="${LAG_MIN:-45}"
API="repos/${REPO}"

HEAD=$(gh api "${API}/commits/main" --jq .sha) || { echo "::error::main の SHA が取れない"; exit 2; }
LAST=$(gh api "${API}/actions/workflows/deployCloudflare.yml/runs?status=success&per_page=1" \
  --jq '.workflow_runs[0].head_sha // ""') || { echo "::error::配信の実行履歴が取れない"; exit 2; }
LATEST_RUN=$(gh api "${API}/actions/workflows/deployCloudflare.yml/runs?per_page=1" \
  --jq '.workflow_runs[0] | "\(.conclusion // .status) \(.html_url)"' 2>/dev/null || echo "不明")

NOW=$(date -u +%s)
if [ -z "$LAST" ]; then
  LAG=99999
  OLDEST="（成功した配信が1件も無い）"
elif [ "$LAST" = "$HEAD" ]; then
  LAG=0
  OLDEST="（未配信なし）"
else
  OLDEST=$(gh api "${API}/compare/${LAST}...${HEAD}" --jq '.commits[0].commit.committer.date') \
    || { echo "::error::未配信コミットの一覧が取れない"; exit 2; }
  LAG=$(( (NOW - $(date -u -d "$OLDEST" +%s)) / 60 ))
fi

SITE_URL="${SITE_URL:-https://${PROJECT}.pages.dev/}"
# 失敗時も curl は -w で 000 を出す。|| で文字を足すと 000000 になるので足さない
HTTP=$(curl -s -o /dev/null -m 20 -w "%{http_code}" "$SITE_URL" || true)
if [ "$HTTP" != "200" ]; then
  sleep 30
  HTTP=$(curl -s -o /dev/null -m 20 -w "%{http_code}" "$SITE_URL" || true)
fi

STALE=0
REASON=""
if [ "$LAG" -gt "$LAG_MIN" ]; then STALE=1; REASON="未配信のコミットが ${LAG} 分たまっている（しきい値 ${LAG_MIN} 分）"; fi
if [ "$HTTP" != "200" ]; then STALE=1; REASON="${REASON:+$REASON / }本番トップが HTTP ${HTTP}"; fi
FORCED=0
if [ "${FORCE_STALE:-}" = "true" ]; then STALE=1; FORCED=1; REASON="${REASON:+$REASON / }起票経路の検証（本番の異常ではない）"; fi

echo "main ${HEAD:0:8} / 最後に配信できたもの ${LAST:0:8} / 未配信の最古 ${OLDEST} / 遅れ ${LAG} 分 / トップ HTTP ${HTTP}"
echo "直近の配信: ${LATEST_RUN}"
echo "判定: stale=${STALE} ${REASON}"

{
  echo "- main: \`${HEAD:0:8}\`"
  echo "- 最後に配信できたコミット: \`${LAST:0:8}\`"
  echo "- 未配信のうち最古のコミット時刻: ${OLDEST}"
  echo "- 遅れ: ${LAG} 分（しきい値 ${LAG_MIN} 分）"
  echo "- 本番トップの応答: HTTP ${HTTP}"
  echo "- 直近の配信の結果: ${LATEST_RUN}"
  [ -n "$REASON" ] && echo "- 判定の理由: ${REASON}"
} > deployLagSummary.md

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "stale=${STALE}"
    echo "forced=${FORCED}"
    echo "lag=${LAG}"
    echo "http=${HTTP}"
  } >> "$GITHUB_OUTPUT"
fi
exit 0
