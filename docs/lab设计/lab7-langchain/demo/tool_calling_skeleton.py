"""
Lab 7.4 — Tool Calling 进阶骨架代码

学员需要完成的内容：
  1. 用 Pydantic 定义结构化工具参数
  2. 实现粗粒度和细粒度两套工具
  3. 对比两种粒度下 Agent 的行为差异
  4. 实现工具异常处理

运行方式：
  python tool_calling_skeleton.py
"""

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "你的百炼 API Key")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"

DATA_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# 数据层
# ---------------------------------------------------------------------------

def load_equipment_data():
    with open(DATA_DIR / "equipment_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_knowledge_base():
    with open(DATA_DIR / "knowledge_base.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Pydantic 参数模型
# ---------------------------------------------------------------------------

class InspectionFilter(BaseModel):
    """巡检记录筛选条件"""
    device_type: Optional[str] = Field(
        default=None,
        description="设备类型，如 变压器、断路器、输电线路、配电柜、开关柜"
    )
    status: Optional[str] = Field(
        default=None,
        description="设备状态：正常运行、异常、停机、维护中"
    )
    region: Optional[str] = Field(
        default=None,
        description="所属区域，如 天河区、海珠区、黄埔区"
    )
    limit: int = Field(
        default=10,
        description="返回的最大记录数"
    )


class FaultDiagnosisInput(BaseModel):
    """故障诊断工具参数"""
    device_id: str = Field(
        description="设备编号，如 EP-B-001"
    )
    symptom: str = Field(
        description="故障现象描述，如 油温过高、断路器拒分、SF6压力低"
    )
    severity: str = Field(
        default="warning",
        description="严重程度：info（一般询问）、warning（需关注）、critical（紧急故障）"
    )


# ---------------------------------------------------------------------------
# 粗粒度工具组（一组大而全的工具）
# ---------------------------------------------------------------------------

from langchain_core.tools import tool


@tool
def search_all_equipment(query: str) -> str:
    """万能搜索工具：输入任意关键词，搜索设备、知识库、巡检记录等所有数据。

    参数:
        query: 任意搜索关键词
    """
    # ===================================================================
    # TODO: 实现粗粒度搜索
    # 问题：参数只有一个 query 字符串，Agent 把什么都塞进来
    # 工具内部需要自己解析意图——你可能需要实现关键词提取
    # 如果 query 太模糊，返回一大堆结果，Agent 难以筛选
    # ===================================================================
    pass


@tool
def inspect_device(query: str) -> str:
    """设备巡检工具：对设备进行检查，返回巡检结果。

    参数:
        query: 描述要检查什么（设备编号、检查类型等全部混在字符串里）
    """
    # ===================================================================
    # TODO: 实现粗粒度巡检工具
    # 问题：所有参数挤在一个字符串里，容易传错
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 细粒度工具组（多个小而专注的工具，含 Pydantic 结构化参数）
# ---------------------------------------------------------------------------

@tool
def search_equipment_by_type(device_type: str) -> str:
    """按设备类型搜索。只按类型筛选，不做其他维度的搜索。

    参数:
        device_type: 设备类型，可选值：变压器、断路器、输电线路、配电柜、开关柜
    """
    # ===================================================================
    # TODO: 实现细粒度搜索 - 只按类型筛选
    # ===================================================================
    pass


@tool
def search_equipment_by_status(status: str) -> str:
    """按设备状态搜索。只按状态筛选。

    参数:
        status: 设备状态，可选值：正常运行、异常、停机、维护中
    """
    # ===================================================================
    # TODO: 实现细粒度搜索 - 只按状态筛选
    # ===================================================================
    pass


@tool
def search_equipment_by_region(region: str) -> str:
    """按区域搜索设备。只按区域筛选。

    参数:
        region: 所属区域，如 天河区、海珠区、黄埔区
    """
    # ===================================================================
    # TODO: 实现细粒度搜索 - 只按区域筛选
    # ===================================================================
    pass


@tool(args_schema=FaultDiagnosisInput)
def diagnose_device_fault(
    device_id: str,
    symptom: str,
    severity: str = "warning",
) -> str:
    """对指定设备进行故障诊断，检索相关知识库并给出处置建议。

    参数:
        device_id: 设备编号
        symptom: 故障现象
        severity: 严重程度
    """
    # ===================================================================
    # TODO: 实现故障诊断
    # 提示：
    #   1. 根据 device_id 查找设备信息
    #   2. 根据 symptom 在知识库中检索相关处理规程
    #   3. 根据 severity 调整建议的紧急程度
    #   4. 返回结构化的诊断结果
    # ===================================================================
    pass


@tool
def get_inspection_records(
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 10,
) -> str:
    """查询巡检记录，支持多维度筛选。

    参数:
        device_type: 设备类型筛选
        status: 设备状态筛选
        region: 区域筛选
        limit: 返回记录数
    """
    # ===================================================================
    # TODO: 实现多维度巡检记录查询
    # 提示：多个参数都是可选的，需要正确处理参数组合
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 对比实验
# ---------------------------------------------------------------------------

def compare_granularity():
    """对比粗粒度和细粒度工具对 Agent 行为的影响

    同一个任务，分别用两套工具：
    1. 创建两个 Agent（粗粒度 vs 细粒度）
    2. 给它们同样的任务
    3. 对比：
       - 工具调用次数
       - 调用参数是否准确
       - Token 消耗
       - 最终答案质量
    """
    # ===================================================================
    # TODO: 完成对比实验
    #
    # 测试任务：
    #   "天河区有哪些设备状态异常？帮我诊断一下这些异常设备可能的原因。"
    #
    # 粗粒度 Agent：可能只调用 search_all_equipment 1 次
    # → 一大堆结果，Agent 自己筛选 → 可能漏掉信息
    #
    # 细粒度 Agent：先调 search_equipment_by_region("天河区")
    # → 再调 search_equipment_by_status("异常")
    # → 再对每台异常设备调 diagnose_device_fault
    # → 多轮调用，但每步结果清晰
    #
    # 输出格式：
    #   维度           | 粗粒度 | 细粒度
    #   工具调用次数    |   ?    |   ?
    #   调用参数准确性  |   ?    |   ?
    #   回答完整性      |   ?    |   ?
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("Lab 7.4 — Tool Calling 进阶骨架")
    print("=" * 50)

    if DASHSCOPE_API_KEY == "你的百炼 API Key":
        print("\n⚠️  请先设置环境变量 DASHSCOPE_API_KEY")
        exit(1)

    llm = ChatOpenAI(
        model=MODEL,
        base_url=DASHSCOPE_BASE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0,
    )

    # TODO: 完成上述函数后，取消以下注释来测试
    # print("\n📋 测试粗粒度工具...")
    # coarse_tools = [search_all_equipment, inspect_device]
    # coarse_agent = create_react_agent(llm, coarse_tools)
    # result = coarse_agent.invoke({
    #     "messages": [{"role": "user", "content": "天河区有哪些设备状态异常？"}]
    # })
    # print(f"粗粒度 Agent 回答: {result['messages'][-1].content[:300]}")

    # print("\n🔧 测试细粒度工具...")
    # fine_tools = [
    #     search_equipment_by_type,
    #     search_equipment_by_status,
    #     search_equipment_by_region,
    #     diagnose_device_fault,
    #     get_inspection_records,
    # ]
    # fine_agent = create_react_agent(llm, fine_tools)
    # result = fine_agent.invoke({
    #     "messages": [{"role": "user", "content": "天河区有哪些设备状态异常？"}]
    # })
    # print(f"细粒度 Agent 回答: {result['messages'][-1].content[:300]}")

    # print("\n📊 对比实验...")
    # compare_granularity()

    print("\n👆 请完成代码中的 TODO 部分，然后取消 main 中的注释来运行")
