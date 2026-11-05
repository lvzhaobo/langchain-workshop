#!/usr/bin/env bash
set -u
cd "$(dirname "$0")" || exit 1
rm -rf .venv
find . -name __pycache__ -type d -not -path './.git/*' -exec rm -rf {} + 2>/dev/null || true
echo "🧹 已清理"
