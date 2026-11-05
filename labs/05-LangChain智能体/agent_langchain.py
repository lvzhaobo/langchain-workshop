"""LangChain ReAct Agent — 定义工具 → 创建 Agent → 观察思考链

首次运行前先建虚拟环境（项目根目录执行一次即可）：
    cd agent-course
    python3 -m venv .venv
    source .venv/bin/activate
    pip install langchain langchain-openai python-dotenv

之后每次运行：
    source ../../.venv/bin/activate
    python agent_langchain.py
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool as lc_tool
from langchain.agents import create_agent

from _mock_llm import scripted, use_mock


@lc_tool
def query_device(device_id: str) -> str:
    """查询设备详情。参数 device_id 如 DEV-0001"""
    devices = {
        "DEV-0001": "华为 AAU5613 | 宏站 | 北京朝阳 | 告警中",
        "DEV-0002": "中兴 AAU8851 | 宏站 | 广州天河 | 运行中",
        "DEV-0003": "爱立信 AIR 6488 | 宏站 | 深圳南山 | 告警中",
    }
    return devices.get(device_id, f"设备 {device_id} 不存在")


@lc_tool
def get_alarms(device_id: str) -> str:
    """查询设备告警。参数 device_id 如 DEV-0001"""
    alarms = {
        "DEV-0001": "[P0] 基站退服 — SCTP链路中断\n[P1] 性能劣化 — 接入成功率降至85%",
        "DEV-0003": "[P2] 传输中断 — 光模块收光功率异常",
    }
    return alarms.get(device_id, "无告警")


@lc_tool
def list_devices(status: str = "") -> str:
    """列出设备清单。参数 status 可选 running/alarm/maintenance"""
    all_devices = [
        ("DEV-0001", "AAU5613", "alarm"),
        ("DEV-0002", "AAU8851", "running"),
        ("DEV-0003", "AIR 6488", "alarm"),
        ("DEV-0004", "BBU5900", "running"),
        ("DEV-0005", "RRU8862", "maintenance"),
    ]
    filtered = [d for d in all_devices if not status or d[2] == status]
    return "\n".join([f"{d[0]} | {d[1]} | {d[2]}" for d in filtered])


def make_agent():
    if use_mock():
        print("⚠️  没检测到 AGENT_API_KEY —— 用预设回复跑通流程（零 Key 模式）")
        print("   想看真模型：填好 .env 里的 AGENT_API_KEY 再跑，代码不用改。\n")
        llm = scripted([
            ("", [{"name": "query_device", "args": {"device_id": "DEV-0001"}, "id": "c1"}]),
            ("", [{"name": "get_alarms", "args": {"device_id": "DEV-0001"}, "id": "c2"}]),
            ("DEV-0001（AAU5613）当前挂 1 条告警：射频单元驻波比异常（major）。"
             "建议先查天馈接头，再复测驻波比。", None),
            ("", [{"name": "list_devices", "args": {"status": "alarm"}, "id": "c3"}]),
            ("", [{"name": "get_alarms", "args": {"device_id": "DEV-0003"}, "id": "c4"}]),
            ("告警设备有两台：DEV-0001 和 DEV-0003。"
             "其中 DEV-0003（AIR 6488）是小区退服（critical），影响面更大，建议优先处置。", None),
        ])
    else:
        llm = ChatOpenAI(
            model=os.getenv("AGENT_MODEL", "deepseek-chat"),
            temperature=0,
            api_key=os.getenv("AGENT_API_KEY"),
            base_url=os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1"),
        )
    return create_agent(
        llm,
        [query_device, get_alarms, list_devices],
        system_prompt="你是排障助手。用工具查询后给出分析结论。",
    )


if __name__ == "__main__":
    agent = make_agent()

    # 测试 1：查单台设备 — Agent 串行调 query_device + get_alarms
    print("\n" + "=" * 50)
    print("测试 1：查单台设备")
    print("=" * 50)
    result1 = agent.invoke({"messages": [("user", "DEV-0001 的状态怎么样？有哪些告警？")]})
    print(result1["messages"][-1].content)

    # 测试 2：找出告警设备 — Agent 先 list_devices 再逐个分析
    print("\n" + "=" * 50)
    print("测试 2：找出告警设备并分析最严重的")
    print("=" * 50)
    result2 = agent.invoke({"messages": [("user", "有哪些设备在告警？把最严重的那台分析一下")]})
    print(result2["messages"][-1].content)
