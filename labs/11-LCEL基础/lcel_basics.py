"""LCEL 基础 — 就两样东西：管道 + 容错

① | 管道符：上一步输出自动成为下一步输入，所有组件统一接口
② 容错方法：.with_fallbacks() 降级 / .with_retry() 重试 / .with_config() 动态调参

价值不在功能多（普通 Python 也能写），在统一接口——
换模型、换 Parser、加降级都不改调用方式，全用 .invoke()/.stream()。

运行：python lcel_basics.py
依赖：pip install langchain langchain-openai requests
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))  # 自动读取课程根目录 .env

import time
import requests
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

# ═══ 配置 ═══
BASE_URL = "http://localhost:8117"
API_KEY = os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY")
API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

from _mock_llm import scripted, use_mock

_ANSWER = ("设备 DEV-0001（华为 AAU5613，望京SOHO）状态：告警。"
           "挂 2 条告警，最高 P0 基站退服（SCTP 链路中断）。建议先查链路。")

if use_mock():
    print("⚠️  没检测到 AGENT_API_KEY —— 用预设回复跑通 LCEL 各部分（零 Key 模式）")
    print("   想看真模型：填好 .env 里的 AGENT_API_KEY 再跑，代码不用改。\n")
    llm = scripted([(_ANSWER, None)] * 20)   # 够用即可，多余的不会被消费
else:
    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        api_key=API_KEY,
        base_url=API_BASE,
    )


# ═══ 获取设备数据（复用 1.1 平台，带兜底） ═══
def fetch_device_info(device_id: str) -> str:
    """从平台获取设备详情文本；平台没起时用内置样例兜底"""
    try:
        resp = requests.get(f"{BASE_URL}/devices/{device_id}", timeout=5)
        data = resp.json()
        if data.get("found"):
            dev = data["device"]
            alarms = dev.get("alarms", [])
            alarm_list = "\n".join([
                f"  - [{a['severity']}] {a['type']}: {a['description']}"
                for a in alarms
            ]) if alarms else "无告警"
            return (f"设备ID：{dev['device_id']}\n"
                    f"厂商/型号：{dev['vendor']} {dev['model']}\n"
                    f"站点：{dev['site']}\n状态：{dev['status']}\n"
                    f"告警（{len(alarms)}条）：\n{alarm_list}")
    except Exception:
        pass

    print("  ⚠️ 平台未连接，使用内置样例设备数据")
    return ("设备ID：DEV-0001\n厂商/型号：华为 AAU5613\n站点：望京SOHO\n状态：告警\n"
            "告警（2条）：\n"
            "  - [P0] 基站退服: SCTP 链路中断导致基站退服\n"
            "  - [P2] 温度告警: 设备温度 78°C，超过阈值")


# ═══════════════════════════════════════════════════════════════
# 第一部分：基础链 — prompt | llm | parser
# ═══════════════════════════════════════════════════════════════

diagnose_prompt = ChatPromptTemplate.from_template(
    """你是 5G 基站运维专家。根据设备数据给出诊断结论（不超过 100 字，结论先行）：

{device_info}""")

basic_chain = diagnose_prompt | llm | StrOutputParser()
#              ↑ 渲染 Prompt    ↑ LLM  ↑ AIMessage → str


# ═══════════════════════════════════════════════════════════════
# 第二部分：RunnableParallel — 一次输入，同时出"诊断 + 工单摘要"
# ═══════════════════════════════════════════════════════════════

ticket_prompt = ChatPromptTemplate.from_template(
    """把以下设备状况压缩成一条工单标题（不超过 30 字，格式：[级别] 站点-设备-问题）：

{device_info}""")

risk_prompt = ChatPromptTemplate.from_template(
    """给以下设备的当前风险打分（0-100，分数越高越危险），只输出：分数 + 一句理由：

{device_info}""")

parallel_chain = RunnableParallel(
    diagnosis=diagnose_prompt | llm | StrOutputParser(),
    ticket_title=ticket_prompt | llm | StrOutputParser(),
    risk_score=risk_prompt | llm | StrOutputParser(),
    raw=RunnablePassthrough(),   # 原始输入原样透传，方便下游使用
)


# ═══════════════════════════════════════════════════════════════
# 第三部分：with_fallbacks — 主模型挂了自动切备用
# ═══════════════════════════════════════════════════════════════

# 故意配一个坏模型模拟"主模型故障"（错误的 api_key）
if use_mock():
    from langchain_core.runnables import RunnableLambda

    def _boom(_):
        raise RuntimeError("模拟主模型故障（零 Key 模式）")

    broken_llm = RunnableLambda(_boom)
else:
    broken_llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        api_key="sk-invalid-key-to-simulate-outage",
        base_url=API_BASE,
        max_retries=0,      # 不重试，快速失败
        timeout=15,
    )

# 备用模型 = 正常配置（真实场景里是另一个厂商/另一个部署）
backup_llm = llm

llm_with_fallback = broken_llm.with_fallbacks([backup_llm])

fallback_chain = diagnose_prompt | llm_with_fallback | StrOutputParser()


# ═══════════════════════════════════════════════════════════════
# 第四部分：with_retry — 瞬时故障自动重试
# ═══════════════════════════════════════════════════════════════

_attempt_counter = {"n": 0}


def flaky_step(x: dict) -> dict:
    """模拟不稳定的中间步骤：前 2 次抛异常，第 3 次成功"""
    _attempt_counter["n"] += 1
    print(f"    flaky_step 第 {_attempt_counter['n']} 次调用...")
    if _attempt_counter["n"] < 3:
        raise ConnectionError("模拟瞬时网络抖动")
    return x


retry_chain = (
    RunnableLambda(flaky_step).with_retry(
        retry_if_exception_type=(ConnectionError,),
        stop_after_attempt=3,
        wait_exponential_jitter=False,
    )
    | diagnose_prompt | llm | StrOutputParser()
)


# ═══ 主程序 ═══
if __name__ == "__main__":
    print("=" * 60)
    print("实验 1.7a：LCEL 基础 — 链、并行、降级、重试")
    print("=" * 60)

    device_info = fetch_device_info("DEV-0001")
    print(f"\n被测设备数据：\n{'-'*40}\n{device_info}\n{'-'*40}")

    # ── 1) 基础链 ──
    print(f"\n{'#'*60}")
    print("# 第一部分：基础链  prompt | llm | parser")
    print(f"{'#'*60}")
    reply = basic_chain.invoke({"device_info": device_info})
    print(reply)

    # ── 2) 并行链 ──
    print(f"\n{'#'*60}")
    print("# 第二部分：RunnableParallel — 诊断 + 工单标题 + 风险评分 同时出")
    print(f"{'#'*60}")

    start = time.time()
    result = parallel_chain.invoke({"device_info": device_info})
    parallel_elapsed = time.time() - start

    print(f"\n【诊断】\n{result['diagnosis']}")
    print(f"\n【工单标题】\n{result['ticket_title']}")
    print(f"\n【风险评分】\n{result['risk_score']}")
    print(f"\n并行总耗时: {parallel_elapsed:.1f}s（三条链同时跑，≈max 而不是 sum）")

    # 串行对照
    start = time.time()
    _ = basic_chain.invoke({"device_info": device_info})
    _ = (ticket_prompt | llm | StrOutputParser()).invoke({"device_info": device_info})
    _ = (risk_prompt | llm | StrOutputParser()).invoke({"device_info": device_info})
    serial_elapsed = time.time() - start
    print(f"串行对照耗时: {serial_elapsed:.1f}s")
    print(f"提速: {serial_elapsed / parallel_elapsed:.1f}x" if parallel_elapsed > 0 else "")

    # ── 3) 降级 ──
    print(f"\n{'#'*60}")
    print("# 第三部分：with_fallbacks — 主模型故障自动切备用")
    print(f"{'#'*60}")
    print("\n主模型配置了无效 API Key（模拟服务故障），观察是否自动降级：")

    start = time.time()
    try:
        reply = fallback_chain.invoke({"device_info": device_info})
        print(f"\n✅ 得到回答（说明已自动切换到备用模型）：")
        print(reply[:150])
        print(f"\n耗时: {time.time()-start:.1f}s（含主模型失败的时间）")
    except Exception as e:
        print(f"\n❌ 主备都失败了：{e}")
        print("   请检查 AGENT_API_KEY 是否配置（备用模型用的是它）")

    # ── 4) 重试 ──
    print(f"\n{'#'*60}")
    print("# 第四部分：with_retry — 瞬时故障自动重试")
    print(f"{'#'*60}")
    print("\nflaky_step 前 2 次会抛 ConnectionError，第 3 次成功：")

    _attempt_counter["n"] = 0
    try:
        reply = retry_chain.invoke({"device_info": device_info})
        print(f"\n✅ 重试后成功，诊断结果：")
        print(reply[:150])
    except Exception as e:
        print(f"\n❌ 重试 3 次后仍失败：{e}")

    # ── 总结 ──
    print(f"\n{'='*60}")
    print("✅ 实验 1.7a 演示完成。")
    print("   核心收获：")
    print("   1. LCEL 的一切都是 Runnable——| 串联、RunnableParallel 并联")
    print("   2. 并行链耗时 ≈ 最慢的那条，不是相加")
    print("   3. .with_fallbacks() 一行代码实现主备降级——生产必配")
    print("   4. .with_retry() 处理瞬时故障——和降级是两类问题（抖动 vs 宕机）")
    print("   下一步：1.7 RunnableBranch 给管道加上'分岔路口'。")
