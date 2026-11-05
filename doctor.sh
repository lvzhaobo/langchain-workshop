#!/usr/bin/env bash
# 环境自检
set -u
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi

echo "python      : $PY"
$PY -V
if $PY -c "import importlib.metadata as m; print('langgraph     :', m.version('langgraph')); print('langchain-core:', m.version('langchain-core')); print('python-dotenv :', m.version('python-dotenv'))" 2>/dev/null; then
  :
else
  echo "❌ 依赖缺失 → ./setup.sh"
fi
echo "uv          : $(command -v uv || echo '未安装（可选）')"
