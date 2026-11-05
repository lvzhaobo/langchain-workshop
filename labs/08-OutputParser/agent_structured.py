"""Output Parser — 让 Agent 输出结构化 JSON 而非自由文本

运行：python agent_structured.py
依赖：pip install langchain langchain-openai pydantic
"""
import os, json
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from _mock_llm import scripted, use_mock
from langchain_core.tools import tool
from langchain.agents import create_agent

# ── ① 定义输出 Schema ──
class DiagnosisResult(BaseModel):
    severity: str = Field(description="严重程度：critical / major / minor / normal")
    root_cause: str = Field(description="可能的根因分析")
    steps: list[str] = Field(description="排查步骤，按优先级排列，至少 3 条")
    escalate: bool = Field(description="是否需要升级为紧急工单")

# ── ② 工具（自包含，同 1.4）──
@tool
def query_device(device_id: str) -> str:
    """查询设备详情。参数 device_id 如 DEV-0001"""
    devices = {
        "DEV-0001": "华为 AAU5613 | 宏站 | 北京朝阳 | 告警中",
        "DEV-0002": "中兴 AAU8851 | 宏站 | 广州天河 | 运行中",
    }
    return devices.get(device_id, f"设备 {device_id} 不存在")

@tool
def get_alarms(device_id: str) -> str:
    """查询设备告警。参数 device_id 如 DEV-0001"""
    alarms = {
        "DEV-0001": "[P0] 基站退服 — SCTP链路中断\n[P1] 性能劣化 — 接入成功率降至85%",
    }
    return alarms.get(device_id, "无告警")


if __name__ == "__main__":
    if use_mock():
        print("⚠️  没检测到 AGENT_API_KEY —— 用预设回复跑通结构化输出（零 Key 模式）")
        print("   想看真模型：填好 .env 里的 AGENT_API_KEY 再跑，代码不用改。\n")
        llm = scripted([
            ("", [{"name": "query_device", "args": {"device_id": "DEV-0001"}, "id": "c1"}]),
            ("", [{"name": "get_alarms", "args": {"device_id": "DEV-0001"}, "id": "c2"}]),
            # 故意在 JSON 外面包了话 —— 这正是「光靠 Prompt 约束不够」的地方
            ("好的，分析结果如下：\n```json\n"
             '{"severity": "critical", "root_cause": "SCTP 链路中断导致基站退服", '
             '"steps": ["检查 SCTP 偶联状态", "核对对端 IP 与 VLAN", "重启 SCTP 偶联并观察"], '
             '"escalate": true}\n```\n如需进一步排查请告诉我。', None),
        ])
    else:
        llm = ChatOpenAI(
            model=os.getenv("AGENT_MODEL", "deepseek-chat"),
            temperature=0,
            api_key=os.getenv("AGENT_API_KEY"),
            base_url=os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1"),
        )

    # ── ③ 创建 Agent，system prompt 里要求输出 JSON ──
    agent = create_agent(
        llm,
        [query_device, get_alarms],
        system_prompt=(
            "你是排障助手。工具查询后，只输出一个 JSON 对象，不要其他文字：\n"
            '{"severity": "critical", "root_cause": "SCTP链路中断", '
            '"steps": ["步骤1", "步骤2", "步骤3"], "escalate": true}'
        ),
    )

    # ── ④ 调用 + 解析 ──
    result = agent.invoke({"messages": [("user", "分析 DEV-0001 的告警并给出诊断")]})
    output = result["messages"][-1].content

    print("原始输出:")
    print(output[:300])
    print()

    # 尝试解析 JSON
    try:
        # 提取 JSON 块（LLM 可能在 JSON 外包裹文字）
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(output[start:end])
            print("解析成功：")
            print(f"  严重程度: {parsed.get('severity', '?')}")
            print(f"  根因: {parsed.get('root_cause', '?')}")
            print(f"  排查步骤: {len(parsed.get('steps', []))} 条")
            print(f"  升级工单: {'是' if parsed.get('escalate') else '否'}")
        else:
            print("（未找到 JSON 块，LLM 没有按格式输出）")
    except Exception as e:
        print(f"（JSON 解析失败：{e}）")
        print("这就是为什么需要 Output Parser——光靠 Prompt 约束不够，还得用 Parser 兜底。")
