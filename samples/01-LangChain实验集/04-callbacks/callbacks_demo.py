"""
实验四：LangChain Callbacks — 回调监控与链路追踪

核心概念：
  - BaseCallbackHandler：LangChain 的回调基类，可 Hook 所有生命周期事件
  - 回调事件链：on_llm_start → on_llm_end → on_tool_start → on_tool_end → ...
  - 实际用途：Token 用量统计、延迟监控、调用链追踪、成本核算

运行方式：
  python 04-callbacks/callbacks_demo.py            # 正常模式
  python 04-callbacks/callbacks_demo.py --offline  # 离线模式
"""

import json
import os
import sys
import time
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
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    class MonitorCallback(BaseCallbackHandler):
        """真实的 LangChain 回调 — BaseCallbackHandler 子类"""

        def __init__(self):
            super().__init__()
            self.llm_calls = []
            self.tool_calls = []
            self._start_time = None

        def on_llm_start(self, serialized, prompts, **kwargs):
            self._start_time = time.time()
            p = prompts[0] if isinstance(prompts, list) else str(prompts)
            print(f"   🟢 [LLM Start] prompt≈{len(str(p))}字符")

        def on_llm_end(self, response, **kwargs):
            elapsed = time.time() - (self._start_time or time.time())
            self._start_time = None
            text = ""
            if hasattr(response, "generations") and response.generations:
                gen = response.generations[0][0]
                text = getattr(gen, "text", "") or str(getattr(gen, "message", ""))
            token_usage = {}
            if hasattr(response, "llm_output") and response.llm_output:
                token_usage = response.llm_output.get("token_usage", {})
            prompt_tokens = token_usage.get("prompt_tokens", len(text) // 4)
            completion_tokens = token_usage.get("completion_tokens", 0)
            self.llm_calls.append({
                "elapsed_ms": round(elapsed * 1000, 1),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            })
            cost = (prompt_tokens / 1000 * 0.002) + (completion_tokens / 1000 * 0.006)
            print(f"   🔴 [LLM End] 耗时={elapsed*1000:.0f}ms, "
                  f"prompt≈{prompt_tokens}t, completion≈{completion_tokens}t, 费用≈¥{cost:.4f}")

        def on_tool_start(self, serialized, input_str, **kwargs):
            name = serialized.get("name", "?")
            self.tool_calls.append({"name": name, "input": str(input_str)[:100], "start_time": time.time()})
            print(f"   🔧 [Tool Start] {name}({str(input_str)[:80]}...)")

        def on_tool_end(self, output, **kwargs):
            if self.tool_calls:
                rec = self.tool_calls[-1]
                elapsed = time.time() - rec["start_time"]
                rec["elapsed_ms"] = round(elapsed * 1000, 1)
                print(f"   🔩 [Tool End] {rec['name']} 耗时={elapsed*1000:.0f}ms")

        def print_summary(self):
            print("\n📊 监控汇总")
            if self.llm_calls:
                total_prompt = sum(c["prompt_tokens"] for c in self.llm_calls)
                total_comp = sum(c["completion_tokens"] for c in self.llm_calls)
                total_tokens = total_prompt + total_comp
                total_cost = (total_prompt / 1000 * 0.002) + (total_comp / 1000 * 0.006)
                avg_latency = sum(c["elapsed_ms"] for c in self.llm_calls) / len(self.llm_calls) if self.llm_calls else 0
                print(f"🤖 LLM 调用：{len(self.llm_calls)}次, Token≈{total_tokens}, 费用≈¥{total_cost:.4f}, 平均延迟={avg_latency:.0f}ms")
            if self.tool_calls:
                print(f"🔧 工具调用：{len(self.tool_calls)}次")
                for tc in self.tool_calls:
                    print(f"   - {tc['name']}: {tc.get('elapsed_ms', '?')}ms")

    @tool
    def search_equipment(keyword: str) -> str:
        equipments = load_equipment_data()
        results = [e for e in equipments if keyword.lower() in e["name"].lower()
                   or keyword.lower() in e["id"].lower() or keyword.lower() in e["type"].lower()
                   or keyword.lower() in e["region"].lower()]
        return json.dumps(results, ensure_ascii=False, indent=2) if results else f"未找到 '{keyword}'"

    @tool
    def get_device_status(device_id: str) -> str:
        for eq in load_equipment_data():
            if eq["id"].upper() == device_id.upper():
                return json.dumps({"name": eq["name"], "status": eq["status"],
                                   "lastCheck": eq["lastCheck"], "checker": eq["checker"]}, ensure_ascii=False)
        return f"未找到 '{device_id}'"

    def run_online():
        if not DASHSCOPE_API_KEY:
            print("\n⚠️  请设置 DASHSCOPE_API_KEY 或使用 --offline"); sys.exit(1)

        monitor = MonitorCallback()
        llm = ChatOpenAI(model=MODEL, base_url=BASE_URL, api_key=DASHSCOPE_API_KEY, temperature=0)
        agent = create_react_agent(llm, [search_equipment, get_device_status])

        print("\n▶️  运行 Agent（LangChain 自动触发回调）...\n")
        print("   LangChain 调用链自动触发 on_llm_start/on_llm_end/on_tool_start/on_tool_end\n")

        for q in ["天河区有哪些设备？", "EP-D-002 巡检人是谁？"]:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": q}]},
                config={"callbacks": [monitor]},
            )
            final_msg = result["messages"][-1]
            print(f"   💬 回答：{final_msg.content[:150]}")

        monitor.print_summary()


# ===========================================================================
# 离线模式
# ===========================================================================

class OfflineMonitor:
    """离线版回调监控 — 纯 Python，不依赖 langchain"""

    def __init__(self):
        self.llm_calls = []
        self.tool_calls = []
        self._start_time = None

    def on_llm_start(self, prompt_text: str):
        self._start_time = time.time()
        chars = len(prompt_text)
        print(f"   🟢 [LLM Start] prompt≈{chars}字符, 估算≈{chars//2} tokens")

    def on_llm_end(self, response_text: str):
        elapsed = time.time() - (self._start_time or time.time())
        self._start_time = None
        prompt_tokens = 200
        completion_tokens = len(response_text) // 2
        cost = (prompt_tokens / 1000 * 0.002) + (completion_tokens / 1000 * 0.006)
        self.llm_calls.append({
            "elapsed_ms": round(elapsed * 1000, 1),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        })
        print(f"   🔴 [LLM End] 耗时={elapsed*1000:.0f}ms, "
              f"prompt≈{prompt_tokens}t, completion≈{completion_tokens}t, 费用≈¥{cost:.4f}")

    def on_tool_start(self, tool_name: str, input_str: str):
        self.tool_calls.append({"name": tool_name, "input": input_str[:80], "start_time": time.time()})
        print(f"   🔧 [Tool Start] {tool_name}({input_str[:60]}...)")

    def on_tool_end(self, output: str):
        if self.tool_calls:
            rec = self.tool_calls[-1]
            elapsed = time.time() - rec["start_time"]
            rec["elapsed_ms"] = round(elapsed * 1000, 1)
            print(f"   🔩 [Tool End] {rec['name']} 耗时={elapsed*1000:.0f}ms")

    def print_summary(self):
        print("\n📊 监控汇总")
        if self.llm_calls:
            total_tokens = sum(c["prompt_tokens"] + c["completion_tokens"] for c in self.llm_calls)
            total_cost = total_tokens / 1000 * 0.004
            avg_latency = sum(c["elapsed_ms"] for c in self.llm_calls) / len(self.llm_calls) if self.llm_calls else 0
            print(f"🤖 LLM 调用：{len(self.llm_calls)}次, Token≈{total_tokens}, 费用≈¥{total_cost:.4f}, 平均延迟={avg_latency:.0f}ms")
        if self.tool_calls:
            print(f"🔧 工具调用：{len(self.tool_calls)}次")
            for tc in self.tool_calls:
                print(f"   - {tc['name']}: {tc.get('elapsed_ms', '?')}ms")


def offline_demo():
    """离线演示：纯 Python 模拟回调事件链"""
    monitor = OfflineMonitor()

    print("\n📖 回调事件链：")
    print("   on_chain_start → on_llm_start → on_llm_end")
    print("                 → on_tool_start → on_tool_end")
    print("                 → on_llm_start → on_llm_end")
    print("                 → on_chain_end\n")

    print("▶️  模拟 Agent 执行（2 次 LLM + 1 次工具调用）...\n")

    # 第一次 LLM
    monitor.on_llm_start("用户问'天河区有哪些设备'，AI 判断需要查数据...")
    time.sleep(0.05)
    monitor.on_llm_end("需要调用 search_equipment 工具查询天河区设备数据。")

    # 工具调用（真实查数据）
    monitor.on_tool_start("search_equipment", "天河区")
    equipments = load_equipment_data()
    results = [e for e in equipments if "天河区" in e["region"]]
    tool_output = json.dumps(results, ensure_ascii=False, indent=2)
    time.sleep(0.01)
    monitor.on_tool_end(tool_output)

    # 第二次 LLM
    monitor.on_llm_start("工具返回了天河区的设备列表，需要组织回答...")
    time.sleep(0.05)
    answer = f"天河区共有{len(results)}台设备：{', '.join(e['name'] + '(' + e['status'] + ')' for e in results)}"
    monitor.on_llm_end(answer)

    print(f"\n💬 最终回答：{answer}")
    monitor.print_summary()

    print("\n💡 回调的实际应用：")
    print("   1. LangSmith 集成 → 远程追踪面板")
    print("   2. 成本告警 → 单日费用超阈值自动通知")
    print("   3. 慢查询分析 → 定位延迟最高的环节")
    print("   4. 审计日志 → 记录每次工具调用的参数和结果")


# ===========================================================================
# 主入口
# ===========================================================================

def main():
    if OFFLINE:
        print("=" * 60)
        print("🧪 实验四：LangChain Callbacks 回调监控 [离线模式]")
        print("=" * 60)
        print("\n  ⚡ 离线模式：纯 Python 模拟回调事件链")
        print("  ⚡ 去掉 --offline 可运行真实 LangChain + BaseCallbackHandler\n")
        offline_demo()
    else:
        print("=" * 60)
        print("🧪 实验四：LangChain Callbacks 回调监控")
        print("=" * 60)
        run_online()

    print("\n" + "=" * 60)
    print("🎉 实验四完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
