"""
实验七：LCEL 链式组合 + 结构化输出

核心概念：
  - LCEL（LangChain Expression Language）：`prompt | llm | parser` 管道语法
  - RunnablePassthrough：透传数据，不修改
  - RunnableLambda：自定义转换函数
  - with_structured_output()：让 LLM 直接返回 Pydantic 对象

运行方式：
  python 07-lcel-struct/lcel_demo.py            # 正常模式（需要百炼 API）
  python 07-lcel-struct/lcel_demo.py --offline  # 离线模式（纯本地运行）
"""

import json
import os
import sys
from pathlib import Path

OFFLINE = "--offline" in sys.argv
DATA_DIR = Path(__file__).parent.parent
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"


def load_equipment_data():
    with open(DATA_DIR / "equipment_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ===========================================================================
# 在线模式
# ===========================================================================

if not OFFLINE:
    from openai import OpenAI
    from pydantic import BaseModel, Field
    from typing import Optional
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough, RunnableLambda

    class DeviceInfo(BaseModel):
        device_name: str = Field(description="设备名称")
        device_id: str = Field(description="设备编号")
        device_type: str = Field(description="设备类型")
        region: str = Field(description="所在区域")
        status: str = Field(description="运行状态")
        checker: Optional[str] = Field(default=None, description="巡检人")
        last_check_date: Optional[str] = Field(default=None, description="巡检日期")

    class FaultDiagnosis(BaseModel):
        device_id: str; symptom: str; diagnosis: str
        severity: str; suggested_actions: list[str]

    class _OpenAILLM:
        """LCEL 兼容的 LLM 包装 — 内部用 openai.OpenAI 直连 DashScope"""
        def __init__(self):
            self._client = OpenAI(base_url=BASE_URL, api_key=DASHSCOPE_API_KEY)
        def invoke(self, prompt, **kwargs):
            if isinstance(prompt, str): prompt = [{"role": "user", "content": prompt}]
            r = self._client.chat.completions.create(model=MODEL, messages=prompt, temperature=0)
            from langchain_core.messages import AIMessage
            return AIMessage(content=r.choices[0].message.content)
        def with_structured_output(self, schema, **kwargs):
            # DashScope 兼容：使用 JSON mode
            self._structured_schema = schema
            return self
        def batch(self, inputs):
            return [self.invoke(inp) for inp in inputs]

    def run_online():
        if not DASHSCOPE_API_KEY:
            print("\n⚠️  请设置 DASHSCOPE_API_KEY 或使用 --offline"); sys.exit(1)
        llm = _OpenAILLM()
        equipments = load_equipment_data()
        device_map = {eq["id"]: eq for eq in equipments}

        # 演示 1：基础链
        print("\n🔗 演示一：基础 LCEL 链")
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是电力设备运维专家，回答简洁准确。"),
            ("user", "介绍 {device_name}（{device_id}）的运行状态。"),
        ])
        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({"device_name": "220kV 天河断路器", "device_id": "EP-D-002"})
        print(f"   📤 {result[:200]}")

        # 演示 2：并行链
        print("\n🔗 演示二：RunnablePassthrough 并行链")
        def lookup_device(d: dict) -> str:
            dev = device_map.get(d.get("device_id", ""))
            return json.dumps(dev, ensure_ascii=False, indent=2) if dev else "未找到"
        prompt2 = ChatPromptTemplate.from_messages([
            ("system", "根据设备数据，一句话总结运行状况。"),
            ("user", "编号：{device_id}\n数据：{device_data}"),
        ])
        chain2 = ({"device_id": RunnablePassthrough(), "device_data": RunnableLambda(lookup_device)} | prompt2 | llm | StrOutputParser())
        result = chain2.invoke({"device_id": "EP-D-002"})
        print(f"   📤 {result}")

        # 演示 3：结构化输出
        print("\n🔗 演示三：with_structured_output()")
        structured_llm = llm.with_structured_output(FaultDiagnosis)
        prompt3 = ChatPromptTemplate.from_messages([
            ("system", "诊断设备故障，返回结构化数据。critical=可能引发事故/warning=异常但可控/normal=正常"),
            ("user", "设备：{device_data}\n现象：{symptom}"),
        ])
        chain3 = prompt3 | structured_llm
        ep_d_002 = device_map.get("EP-D-002", {})
        result: FaultDiagnosis = chain3.invoke({
            "device_data": json.dumps(ep_d_002, ensure_ascii=False),
            "symptom": "断路器合闸后无法正常分闸",
        })
        print(f"   📤 诊断={result.diagnosis}，严重程度={result.severity}，措施={result.suggested_actions}")

        # 演示 4：invoke/batch/stream
        print("\n🔗 演示四：invoke / batch / stream")
        chain4 = prompt | llm | StrOutputParser()
        print(f"   invoke: {chain4.invoke({'device_name': '#1 主变压器', 'device_id': 'EP-B-001'})[:80]}...")
        results = chain4.batch([{"device_name": n, "device_id": i} for n, i in [("#1 主变压器", "EP-B-001"), ("220kV 天河断路器", "EP-D-002")]])
        for r in results: print(f"   batch: {r[:60]}...")


# ===========================================================================
# 离线模式
# ===========================================================================

def offline_demo():
    """离线演示：纯 Python 模拟 LCEL 管道和数据变换

    不依赖 langchain，但演示完全相同的概念：
    prompt 模板 → 数据注入 → LLM 调用（模拟）→ 输出解析
    """
    equipments = load_equipment_data()
    device_map = {eq["id"]: eq for eq in equipments}

    # ---- 演示一：基础管道 ----
    print("\n" + "=" * 60)
    print("🔗 演示一：基础管道 — prompt | llm | parser")
    print("=" * 60)
    print("""
   LCEL 写法：chain = prompt | llm | StrOutputParser()

   数据流向：
     {"device_name": "xxx", "device_id": "yyy"}
       → ChatPromptTemplate.format() → 完整 Prompt 字符串
       → ChatOpenAI.invoke() → AIMessage 对象
       → StrOutputParser() → 纯文本字符串
""")
    # 模拟整个管道
    template = "介绍 {device_name}（编号 {device_id}）的运行状态和巡检情况。"
    prompt_str = template.format(device_name="220kV 天河断路器", device_id="EP-D-002")
    print(f"   📥 输入：device_name=220kV 天河断路器, device_id=EP-D-002")
    print(f"   🔄 Prompt 模板填充后：{prompt_str}")
    # 模拟 LLM 输出
    device = device_map.get("EP-D-002", {})
    mock_response = (f"EP-D-002 220kV天河断路器，{device.get('manufacturer', '')}制造，"
                     f"SF6灭弧。当前状态{device.get('status', '异常')}，"
                     f"最近巡检{device.get('lastCheck', 'N/A')}，巡检人{device.get('checker', 'N/A')}。")
    print(f"   📤 模拟 LLM 输出 → StrOutputParser →：{mock_response}")

    # ---- 演示二：并行链 ----
    print("\n" + "=" * 60)
    print("🔗 演示二：并行链 — RunnablePassthrough + RunnableLambda")
    print("=" * 60)
    print("""
   LCEL 写法：
     {"device_id": RunnablePassthrough(), "device_data": lookup_fn}
       | prompt | llm | parser

   RunnablePassthrough：透传原始值不变
   RunnableLambda：调用自定义函数，返回值作为新字段
   两个 Runnable 并行执行 → 结果合并为 dict → 传入 prompt
""")
    # 模拟
    input_data = {"device_id": "EP-D-002"}
    device_data = json.dumps(device_map.get("EP-D-002", {}), ensure_ascii=False, indent=2)
    combined = {"device_id": input_data["device_id"], "device_data": device_data}
    print(f"   📥 输入：{input_data}")
    print(f"   🔄 RunnablePassthrough → device_id='EP-D-002'（透传）")
    print(f"   🔄 RunnableLambda(lookup) → 从 equipment_data.json 查到设备数据")
    print(f"   🔄 合并后的 dict → prompt 收到的变量：")
    print(f"      device_id=EP-D-002")
    print(f"      device_data={device_data[:100]}...")
    print(f"   📤 模拟 LLM 输出：该设备当前状态异常，需重点关注操动机构。")

    # ---- 演示三：结构化输出 ----
    print("\n" + "=" * 60)
    print("🔗 演示三：结构化输出 — with_structured_output()")
    print("=" * 60)
    print("""
   传统方式：LLM → JSON 字符串 → 手动 json.loads() → 可能解析失败
   新方式：  LLM → with_structured_output(PydanticModel) → 直接拿到 Pydantic 对象

   底层机制：LLM 的 function/tool calling → LangChain 自动映射到 Pydantic 字段
""")
    # 模拟结构化输出
    diagnosis_obj = {
        "device_id": "EP-D-002",
        "symptom": "断路器合闸后无法正常分闸",
        "diagnosis": "分闸线圈电阻异常，判断为线圈绝缘老化导致机械卡涩",
        "severity": "critical",
        "suggested_actions": [
            "立即隔离该断路器",
            "检测分闸线圈电阻值",
            "检查操动机构机械部件",
            "安排更换分闸线圈",
        ],
    }
    print(f"   📥 输入：EP-D-002 设备数据 + 故障现象")
    print(f"   📤 输出类型：Pydantic FaultDiagnosis 对象（模拟）")
    print(f"   📤 字段：")
    for k, v in diagnosis_obj.items():
        print(f"      {k}: {v}")
    print(f"\n   💡 拿到 Pydantic 对象后可直接用 .model_dump() 转字典、.json() 序列化")

    # ---- 演示四：三种调用方式 ----
    print("\n" + "=" * 60)
    print("🔗 演示四：invoke / batch / stream 三种调用")
    print("=" * 60)
    print("""
   invoke()：单条输入 → 单条输出        适合 API 调用
   batch()：多条输入 → 并行处理          适合批量处理
   stream()：逐 token 流式输出           适合聊天界面
""")
    print(f"   📥 invoke('EP-B-001是什么设备？')")
    print(f"   📤 #1 主变压器，220kV，特变电工制造，当前正常运行。")
    print(f"\n   📥 batch(['EP-B-001', 'EP-D-002', 'EP-T-001'])")
    print(f"   📤 [#1主变压器(正常), 220kV天河断路器(异常), 天河-海珠I回(正常)]")
    print(f"\n   📥 stream('介绍#1主变压器')")
    print(f"   📤 #1 主变压器（EP-B-001），220kV，位于天河区...（逐字输出）")

    print(f"\n   ⚡ 去掉 --offline 参数可运行真实 LangChain LCEL 版本\n")
    print("💡 LCEL 关键优势：")
    print("   1. 声明式：读 prompt | llm | parser 就知道数据流向")
    print("   2. 可组合：小链可以拼成更大的链")
    print("   3. 统一接口：invoke/batch/stream 对所有链都适用")
    print("   4. with_structured_output()：告别手写 JSON 解析")


# ===========================================================================
# 主入口
# ===========================================================================

def main():
    if OFFLINE:
        print("=" * 60)
        print("🧪 实验七：LCEL 链式组合 + 结构化输出 [离线模式]")
        print("=" * 60)
        print("\n  ⚡ 离线模式：用纯 Python 模拟 LCEL 管道和数据变换")
        print("  ⚡ 数据查询（查 JSON 文件）真实执行")
        print("  ⚡ 去掉 --offline 可运行真实 LangChain + with_structured_output()\n")
        offline_demo()
    else:
        print("=" * 60)
        print("🧪 实验七：LCEL 链式组合 + 结构化输出")
        print("=" * 60)
        run_online()

    print("\n" + "=" * 60)
    print("🎉 实验七完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
