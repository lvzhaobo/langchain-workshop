#!/usr/bin/env bash
# 建 .venv 并装依赖。macOS。
set -eu
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then
    echo "→ 用 uv 建 venv（Python 3.11）"
    uv venv --python 3.11 .venv
  else
    echo "→ 没装 uv，用系统 Python 建 venv"
    python3 -m venv .venv
  fi
fi

echo "→ 安装依赖"
if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python -q -r requirements.txt
else
  .venv/bin/python -m pip install -q -r requirements.txt
fi

echo "✅ 装好了。下一步：./run.sh lab-01"
