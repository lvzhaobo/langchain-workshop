"""
Lab 7.1 — Agent 骨架代码

学员需要完成的内容：
  1. _search_equipment 工具函数体
  2. create_agent 调用
  3. 对比实验：单次 LLM vs Agent

运行方式：
  python agent_skeleton.py
"""

import json
import os
from pathlib import Path

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "你的百炼 API Key")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"

DATA_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# 工具数据层
# ---------------------------------------------------------------------------

def load_equipment_data():
    """从 JSON 文件加载设备数据"""
    with open(DATA_DIR / "equipment_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------

from langchain_core.tools import tool


@tool
def search_equipment(keyword: str) -> str:
    """搜索电力设备。输入设备名称、编号、类型或区域的任意关键词，返回匹配的设备列表。

    参数:
        keyword: 搜索关键词，如 '#1 主变压器'、'EP-D-001'、'断路器'、'天河区'
    """
    # ===================================================================
    # TODO: 完成搜索逻辑
    # 1. 调用 load_equipment_data() 获取设备列表
    # 2. 遍历设备，将 keyword 与 name、id、type、region 逐一比对
    # 3. 返回格式化的搜索结果字符串（JSON 格式）
    # ===================================================================
    pass


# =======================================================================
# 提示：以上 search_equipment 函数已经用 @tool 装饰器标记。
# @tool 的作用：
#   1. 将普通 Python 函数注册为 LangChain 可调用的工具
#   2. 函数的 docstring（"""..."""）会自动作为工具描述传给 AI，AI 根据描述决定何时调用
#   3. 函数的参数类型标注（如 keyword: str）会告诉 AI 传入什么参数
# =======================================================================


# ---------------------------------------------------------------------------
# Agent 创建
# ---------------------------------------------------------------------------

def build_agent():
    """创建 Agent"""
    # ===================================================================
    # TODO: 创建 LLM 实例和 Agent
    # 1. 用 ChatOpenAI 创建 LLM，需要传 base_url 和 api_key
    # 2. 用 create_react_agent 创建 Agent，传入 LLM 和工具列表
    # 3. 返回 agent
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 对比实验
# ---------------------------------------------------------------------------

def compare_llm_vs_agent():
    """对比：同一问题，单次 LLM 调用 vs Agent"""
    # ===================================================================
    # TODO: 完成对比实验
    # 1. 用 LLM.invoke 直接问 "天河区有哪些设备？"，观察结果
    # 2. 用 agent.invoke 问同样的问题，观察 Agent 是否调用了工具
    # 3. 打印两者的回答，对比差异
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("Lab 7.1 — 基础 LangChain Agent 骨架")
    print("=" * 50)

    # 检查 API Key
    if DASHSCOPE_API_KEY == "你的百炼 API Key":
        print("\n⚠️  请先设置环境变量 DASHSCOPE_API_KEY")
        print("   export DASHSCOPE_API_KEY=sk-...")
        exit(1)

    # TODO: 完成上述函数后，取消以下注释来测试
    # print("\n📋 设备数据加载测试...")
    # data = load_equipment_data()
    # print(f"   共加载 {len(data)} 台设备")

    # print("\n🔍 工具测试：search_equipment...")
    # result = search_equipment.invoke("变压器")
    # print(f"   搜索结果：{result[:200]}...")

    # print("\n🤖 创建 Agent...")
    # agent = build_agent()

    # print("\n📊 对比实验：LLM vs Agent")
    # compare_llm_vs_agent()

    print("\n👆 请完成代码中的 TODO 部分，然后取消 main 中的注释来运行")
