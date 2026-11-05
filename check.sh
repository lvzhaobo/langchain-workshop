#!/usr/bin/env bash
# 验收某个 lab：./check.sh lab-01      查你的 main.py
#               ./check.sh lab-01 -s   查参考答案
set -u
cd "$(dirname "$0")" || exit 1
. scripts/_resolve.sh
[ -x .venv/bin/python ] || { echo "❌ 先跑 ./setup.sh"; exit 1; }

target=${1:-}
[ -z "${target}" ] && { echo "用法: ./check.sh <lab> [-s]"; exit 1; }
dir=$(resolve_lab "${target}") || { echo "❌ 找不到 ${target}"; exit 1; }

case "${2:-}" in
  -s|--solution)
    echo "▶ 验收 ${dir}  [参考答案]"
    exec .venv/bin/python "${dir}/check.py" --solution
    ;;
  *)
    echo "▶ 验收 ${dir}  [你的代码]"
    exec .venv/bin/python "${dir}/check.py"
    ;;
esac
