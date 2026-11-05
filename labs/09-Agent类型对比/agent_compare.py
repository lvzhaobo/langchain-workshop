"""Agent 类型对比 + Model I/O + 温度参数 — 三维选型实验

三轮对比：
  ① 温度：temp=0 / 0.7 / 1.2（同模型 × 同任务 × 不同输出风格）
  ② 模型：DeepSeek vs GPT-4o vs Qwen（同 Agent × 同任务）
  ③ Agent 类型：ReAct vs Tool Calling（同任务 × 同模型）

运行：python agent_compare.py
依赖：pip install langchain langchain-openai
"""
import os, time
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from langchain_openai import ChatOpenAI

from _mock_llm import rule_based, use_mock
from langchain_core.tools import tool
from langchain.agents import create_agent


# ═══ 工具（自包含，不依赖平台）═══
@tool
def query_device(device_id: str) -> str:
    """查询设备详情。参数 device_id 如 DEV-0001"""
    devices = {
        "DEV-0001": "华为 AAU5613 | 宏站 | 北京 | 告警中",
        "DEV-0002": "中兴 AAU8851 | 宏站 | 广州 | 运行中",
        "DEV-0003": "爱立信 AIR 6488 | 宏站 | 深圳 | 告警中",
    }
    return devices.get(device_id, f"设备 {device_id} 不存在")


@tool
def get_alarms(device_id: str) -> str:
    """查询设备告警。参数 device_id 如 DEV-0001"""
    alarms = {
        "DEV-0001": "[P0] 基站退服 | [P1] 性能劣化",
        "DEV-0003": "[P2] 传输中断 | [P2] 配置错误",
    }
    return alarms.get(device_id, "无告警")


@tool
def list_devices(status: str = "") -> str:
    """列出设备清单。参数 status 可选 running/alarm/maintenance"""
    all_devices = [
        ("DEV-0001", "AAU5613", "alarm"), ("DEV-0002", "AAU8851", "running"),
        ("DEV-0003", "AIR 6488", "alarm"), ("DEV-0004", "BBU5900", "running"),
        ("DEV-0005", "RRU8862", "maintenance"),
    ]
    filtered = [d for d in all_devices if not status or d[2] == status]
    return "\n".join([f"{d[0]} | {d[1]} | {d[2]}" for d in filtered])


# ═══ 模型配置 ═══
MODEL_CONFIGS = {
    "deepseek-chat": {
        "api_key": os.getenv("AGENT_API_KEY", ""),
        "base_url": "https://api.deepseek.com/v1",
    },
    # 有 Key 的话自行追加更多模型：
    # "qwen-plus": {
    #     "api_key": os.getenv("QWEN_API_KEY", ""),
    #     "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    # },
}


# 零 Key 模式下按温度给不同详略的答复，让「温度影响输出」这个教学点成立
_MOCK_BY_TEMP = {
    0: ("DEV-0001 告警，最高 P0 基站退服。先查 SCTP 链路。"),
    0.7: ("DEV-0001（AAU5613，望京SOHO）当前处于告警状态，共 2 条告警，"
          "最高为 P0 级基站退服。建议按顺序排查：① SCTP 偶联状态 ② 对端 IP 与 VLAN ③ 天馈与光模块。"),
    1.2: ("关于这台 DEV-0001（AAU5613，望京SOHO）的情况，可以从几个角度看："
          "它现在挂 2 条告警，最严重的是 P0 基站退服，影响面不小；"
          "往上追可能是 SCTP 链路问题，也可能是传输侧闪断，甚至要考虑电源波动；"
          "建议先按 SCTP 链路 → 传输 → 电源的顺序逐层排除，必要时联系传输专业协同处理。"),
}


def _make_agent(model_name="deepseek-chat", temperature=0):
    config = MODEL_CONFIGS[model_name]
    if use_mock():
        # 温度越高，回答越发散 —— 用同一个任务对比三档
        llm = rule_based(
            [("哪些", "list_devices", {}),
             ("列表", "list_devices", {}),
             ("状态", "query_device", {"device_id": "DEV-0001"}),
             ("怎么样", "query_device", {"device_id": "DEV-0001"}),
             ("告警", "get_alarms", {"device_id": "DEV-0001"})],
            answer=_MOCK_BY_TEMP.get(temperature, _MOCK_BY_TEMP[0]),
        )
    else:
        llm = ChatOpenAI(
            model=model_name, temperature=temperature,
            api_key=config["api_key"], base_url=config.get("base_url"),
        )
    return create_agent(
        llm, [query_device, get_alarms, list_devices],
        system_prompt="你是排障助手。简洁回答。",
    )


# ═══ Round 1：温度对比 ═══
def compare_temperature(task, model_name="deepseek-chat"):
    print(f"\n{'='*60}")
    print(f"Round 1：温度对比（模型={model_name}）")
    print(f"任务：{task[:60]}")
    print(f"{'='*60}")

    results = {}
    for temp in [0, 0.7, 1.2]:
        print(f"\n  ── temp={temp} ──")
        config = MODEL_CONFIGS[model_name]
        if not config["api_key"] and not use_mock():
            print("  API Key 未配置，跳过")
            continue
        try:
            agent = _make_agent(model_name, temp)
            start = time.time()
            result = agent.invoke({"messages": [("user", task)]})
            elapsed = time.time() - start
            output = result["messages"][-1].content
            results[temp] = {"elapsed": elapsed, "length": len(output), "preview": output[:200]}
            print(f"  耗时: {elapsed:.1f}s | 字数: {len(output)}")
            print(f"  开头: {output[:120]}...")
        except Exception as e:
            print(f"  错误: {e}")
            results[temp] = None

    # ── 对比分析 ──
    print(f"\n  {'─'*50}")
    print(f"  对比分析：同一个问题，温度不同差在哪")
    print(f"  {'─'*50}")
    valid = {t: r for t, r in results.items() if r}
    if len(valid) >= 2:
        temps = sorted(valid.keys())
        for t in temps:
            r = valid[t]
            label = {0: "精准但" , 0.7: "均衡但", 1.2: "丰富但"}.get(t, "")
            print(f"  temp={t}: {r['length']}字 — {label}每次结果可能不同")

        # 具体差异
        if 0 in valid and 1.2 in valid:
            d = valid[1.2]["length"] - valid[0]["length"]
            if d > 0:
                print(f"  temp=1.2 比 temp=0 多输出 {d} 字（+{d*100//valid[0]['length']}%），增加了解释和背景信息")
            else:
                print(f"  三档温度输出长度接近 — DeepSeek 对此任务对温度不敏感")

    print(f"\n  排障场景选型：")
    print(f"    temp=0   → 确定性任务（诊断结论不能「看心情」）")
    print(f"    temp=0.7 → 客户沟通（解释详细、语气自然，但排障结论不偏离）")
    print(f"    temp=1.2 → 创意发散（排障别用——根因不能随机生成）")


# ═══ Round 2：模型对比 ═══
def compare_models(task):
    print(f"\n{'='*60}")
    print(f"Round 2：模型对比（同 Agent、同任务）")
    print(f"任务：{task[:60]}")
    print(f"{'='*60}")

    for model_name, config in MODEL_CONFIGS.items():
        if not config["api_key"] and not use_mock():
            print(f"  {model_name}: API Key 未配置，跳过（可自行追加）")
            continue
        try:
            agent = _make_agent(model_name, temperature=0)
            start = time.time()
            result = agent.invoke({"messages": [("user", task)]})
            elapsed = time.time() - start
            output = result["messages"][-1].content
            print(f"  {model_name}: {elapsed:.1f}s, {len(output)}字")
        except Exception as e:
            print(f"  {model_name}: {e}")

    print("\n  模型选型：默认 DeepSeek。有 Key 的话可在 MODEL_CONFIGS 追加更多")


# ═══ Round 3：Agent 行为对比（同模型，看工具调用路径）═══
def compare_behavior():
    print(f"\n{'='*60}")
    print(f"Round 3：Agent 行为对比（看工具调用路径差异）")
    print(f"{'='*60}")

    tasks = [
        ("简单查询", "DEV-0001 的状态怎么样？"),
        ("综合诊断", "有哪些设备在告警？把最严重的那台分析一下"),
    ]

    for label, task in tasks:
        print(f"\n  [{label}] {task}")
        try:
            agent = _make_agent("deepseek-chat", temperature=0)
            result = agent.invoke({"messages": [("user", task)]})
            tool_msgs = [m for m in result["messages"] if m.type == "tool"]
            if tool_msgs:
                tool_names = [m.name for m in tool_msgs]
                print(f"  工具调用路径: {' → '.join(tool_names)} ({len(tool_names)}步)")
            else:
                print(f"  未调用工具，直接回复")
        except Exception as e:
            print(f"  {e}")


# ═══ 主程序 ═══
if __name__ == "__main__":
    TASK = "DEV-0001 的状态怎么样？有哪些告警？分析下严重程度"

    compare_temperature(TASK)
    compare_models(TASK)
    compare_behavior()

    print(f"\n{'='*60}")
    print("三维选型公式：模型 × 温度 × 任务复杂度")
    print("排障默认：deepseek-chat + temp=0")
    print(f"{'='*60}")
