#!/usr/bin/env bash
# 跑一个 lab：./run.sh 01  或  ./run.sh 27-LangGraph多Agent
set -eu
cd "$(dirname "$0")" || exit 1
. scripts/_resolve.sh
[ -x .venv/bin/python ] || { echo "❌ 先跑 ./setup.sh"; exit 1; }

list_labs() { for d in labs/[0-9][0-9]-*; do [ -d "$d" ] && echo "  $(basename "$d")"; done; }

target=${1:-}
if [ -z "${target}" ]; then
  echo "用法: ./run.sh <编号|名称>"; echo; echo "可用："; list_labs; exit 0
fi

dir=$(resolve_lab "${target}") || { echo "❌ 找不到 ${target}"; echo "可用："; list_labs; exit 1; }

# 入口：优先 main.py；没有就挑唯一的 py；多个则列出来让用户选
entry="${dir}/main.py"
if [ ! -f "${entry}" ]; then
  # 排除辅助文件：_ 开头的、check.py（验收脚本）、solution.py（参考答案）
  pys=$(find "${dir}" -maxdepth 1 -name '*.py' ! -name '_*' ! -name 'check.py' ! -name 'solution.py' | sort)
  n=$(echo "${pys}" | grep -c . || true)
  if [ "${n}" -eq 1 ]; then entry="${pys}"
  elif [ "${n}" -eq 0 ]; then echo "⚠️  ${dir} 没有可运行的 .py（可能是纯文档实验）"; exit 1
  else
    echo "⚠️  ${dir} 有多个入口，请指定："
    echo "${pys}" | sed 's|^|  |'
    echo; echo "例：.venv/bin/python ${dir}/<文件名>.py"
    exit 1
  fi
fi

echo "▶ ${entry}"
exec .venv/bin/python "${entry}"
