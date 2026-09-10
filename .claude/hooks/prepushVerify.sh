#!/usr/bin/env bash
# prepushVerify.sh — PreToolUse フックの入口（本体は prepushVerify.py）。
# 1) 入力に "push" の文字が無ければ git push ではあり得ないので、python を起動せずに通す。
# 2) それ以外は prepushVerify.py に渡す。python が見つからない・起動しないときは
#    「検算が走らなかった」として exit 2（ブロック）。0 以外はすべて 2 に寄せる。
input=$(cat) || { echo "[prepushVerify] BLOCK: フック入力を読めない。未検証は合格にしない。" >&2; exit 2; }
case "$input" in
  *push*) ;;
  *) exit 0 ;;
esac
dir=$(cd "$(dirname "$0")" && pwd) || { echo "[prepushVerify] BLOCK: フックの場所を解決できない。" >&2; exit 2; }
for py in "${BOATRACE_PYTHON:-}" "${LOCALAPPDATA:-}/Python/bin/python.exe" python3 python; do
  [ -n "$py" ] || continue
  "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1 || continue
  printf '%s' "$input" | "$py" "$dir/prepushVerify.py"
  rc=$?
  [ "$rc" -eq 0 ] && exit 0
  [ "$rc" -eq 2 ] || echo "[prepushVerify] BLOCK: 検算スクリプトが rc=$rc で終了。未検証は合格にしない。" >&2
  exit 2
done
echo "[prepushVerify] BLOCK: python を起動できない＝検算が走らない。未検証は合格にしない。" >&2
exit 2
