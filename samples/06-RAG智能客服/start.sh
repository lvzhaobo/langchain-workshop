#!/bin/bash
# LangChain RAG 智能客服系统启动脚本

echo "========================================"
echo "LangChain RAG 智能客服系统"
echo "========================================"

# 检查是否设置了 OPENAI_API_KEY
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  请先设置 OPENAI_API_KEY 环境变量"
    echo "示例: export OPENAI_API_KEY='your-api-key'"
    exit 1
fi

# 进入后端目录
cd backend

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 安装依赖..."
pip install -r requirements.txt

# 启动服务
echo ""
echo "🚀 启动服务..."
echo "========================================"
echo "API地址: http://localhost:8000"
echo "前端界面: http://localhost:8000/frontend/index.html"
echo "API文档: http://localhost:8000/docs"
echo "========================================"
echo ""

python main.py