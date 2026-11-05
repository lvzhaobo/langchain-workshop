#!/usr/bin/env bash
# 验收所有「已适配」的 lab（有 check.py 的）。未适配的不算失败，单独计数。
set -u
cd "$(dirname "$0")" || exit 1
[ -x .venv/bin/python ] || { echo "❌ 先跑 ./setup.sh"; exit 1; }

ok=0; skip=0; fail=0; failed=""
for d in labs/[0-9][0-9]-*; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  if [ ! -f "$d/check.py" ]; then
    skip=$((skip+1)); continue
  fi
  if .venv/bin/python "$d/check.py" --solution >/dev/null 2>&1; then
    printf '  ✅ %s\n' "$name"; ok=$((ok+1))
  else
    printf '  ❌ %s\n' "$name"; fail=$((fail+1)); failed="$failed $name"
  fi
done

echo
echo "─────────────────────────────────────────"
printf '  ✅ %d 通过    ⬜ %d 未适配    ❌ %d 失败\n' "$ok" "$skip" "$fail"
[ "$fail" -gt 0 ] && echo "  失败：$failed"
echo "─────────────────────────────────────────"
[ "$fail" -eq 0 ]
