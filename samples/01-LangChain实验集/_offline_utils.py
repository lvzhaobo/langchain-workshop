"""
离线模式共享工具 — 所有实验共用

用法：
  from _offline_utils import should_offline, mock_llm_response, print_offline_banner
  OFFLINE = should_offline()

运行方式：
  python 01-agent-basic/agent_basic.py           # 正常模式（需要百炼 API）
  python 01-agent-basic/agent_basic.py --offline # 离线模式（无需任何 API）

离线模式行为：
  - 不调用任何外部 API
  - 打印完整的流程和数据变换
  - 用预设的模拟响应代替 LLM 返回
  - 代码结构、数据流、错误处理全部保持真实
"""

import json
import sys

# ---------------------------------------------------------------------------
# 离线模式检测
# ---------------------------------------------------------------------------

def should_offline() -> bool:
    """检查命令行参数中是否有 --offline"""
    return "--offline" in sys.argv


# ---------------------------------------------------------------------------
# 离线横幅
# ---------------------------------------------------------------------------

def print_offline_banner(experiment_name: str):
    """打印离线模式提示"""
    print(f"\n  ⚡ 离线模式运行中（{experiment_name}）")
    print(f"  ⚡ 所有 API 调用已替换为本地模拟响应")
    print(f"  ⚡ 去掉 --offline 参数即可使用真实百炼 API\n")


# ---------------------------------------------------------------------------
# 模拟 LLM 响应
# ---------------------------------------------------------------------------

def mock_llm_response(prompt_text: str, *, role: str = "diagnosis") -> str:
    """根据 prompt 内容返回一个看起来合理的模拟响应

    不同 role 会返回不同风格的响应，让离线演示更真实。
    """
    prompt_lower = prompt_text.lower()

    # === 设备相关 ===
    if "ep-b-001" in prompt_lower or "#1 主变压器" in prompt_text:
        return _device_ep_b_001_response(role)
    elif "ep-d-002" in prompt_lower or "天河断路器" in prompt_text:
        return _device_ep_d_002_response(role)
    elif "天河区" in prompt_text:
        return _region_tianhe_response(role)
    elif "变压器" in prompt_text and ("搜索" in prompt_text or "查找" in prompt_text):
        return _search_transformer_response()
    elif "断路器" in prompt_text and "拒分" in prompt_text:
        return _breaker_fault_response(role)

    # === 诊断相关 ===
    if "诊断" in prompt_text and "故障" in prompt_text:
        return _diagnosis_response(role)
    if "方案" in prompt_text or "处置" in prompt_text:
        return _solution_response(role)
    if "巡检" in prompt_text or "执行" in prompt_text or "记录" in prompt_text:
        return _execute_response(role)

    # === 统计/汇总 ===
    if "统计" in prompt_text or "汇总" in prompt_text:
        return _summary_response()
    if "分析" in prompt_text and "设备" in prompt_text:
        return _analysis_response()

    # === Supervisor 决策 ===
    if "下一步" in prompt_text or "supervisor" in prompt_lower:
        return _supervisor_decision(prompt_text)

    # === 摘要 ===
    if "摘要" in prompt_text:
        return "对话摘要：#1主变压器EP-B-001，油温78°C异常，冷却风扇转速偏慢，油位下降5%，上月DGA乙炔升高。建议降负荷运行并安排DGA复测。"

    # === 默认 ===
    return _default_response(role)


def _device_ep_b_001_response(role: str) -> str:
    if role == "extract":
        return json.dumps({"device_name": "#1 主变压器", "device_id": "EP-B-001", "device_type": "变压器", "region": "天河区", "status": "正常运行", "checker": "张工", "last_check_date": "2026-07-10"}, ensure_ascii=False)
    return "EP-B-001 #1主变压器，220kV，天河区，特变电工制造，容量180MVA，油浸风冷。当前正常运行，最近巡检2026-07-10，巡检人张工。"


def _device_ep_d_002_response(role: str) -> str:
    if role == "extract":
        return json.dumps({"device_name": "220kV 天河断路器", "device_id": "EP-D-002", "device_type": "断路器", "region": "天河区", "status": "异常", "checker": "王工", "last_check_date": "2026-07-07"}, ensure_ascii=False)
    return "EP-D-002 220kV天河断路器，西门子制造，SF6灭弧。当前状态异常，最近巡检2026-07-07，巡检人王工。需要立即排查拒分故障。"


def _region_tianhe_response(role: str) -> str:
    return "天河区共有5台设备：#1主变压器(EP-B-001,正常)、#2主变压器(EP-B-002,正常)、220kV天河断路器(EP-D-002,异常)、天河-海珠I回(EP-T-001,正常)、天河站10kV配电柜A(EP-P-001,正常)。"


def _search_transformer_response() -> str:
    return json.dumps([
        {"id": "EP-B-001", "name": "#1 主变压器", "type": "变压器", "region": "天河区", "voltage": "220kV", "status": "正常运行", "checker": "张工"},
        {"id": "EP-B-002", "name": "#2 主变压器", "type": "变压器", "region": "天河区", "voltage": "220kV", "status": "正常运行", "checker": "张工"},
        {"id": "EP-B-003", "name": "#3 备用变压器", "type": "变压器", "region": "海珠区", "voltage": "110kV", "status": "维护中", "checker": "李工"},
        {"id": "EP-B-004", "name": "#4 主变压器", "type": "变压器", "region": "黄埔区", "voltage": "220kV", "status": "正常运行", "checker": "张工"},
    ], ensure_ascii=False, indent=2)


def _breaker_fault_response(role: str) -> str:
    if role == "diagnosis":
        return json.dumps({"device_id": "EP-D-002", "symptom": "断路器拒分故障", "diagnosis": "分闸线圈电阻异常，可能因长期运行导致线圈绝缘老化或机械卡涩", "severity": "critical", "suggested_actions": ["立即隔离该断路器", "检测分闸线圈电阻值", "检查操动机构机械部件", "安排更换分闸线圈"]}, ensure_ascii=False)
    return ("诊断结论：EP-D-002断路器分闸线圈电阻异常，判断为线圈绝缘老化导致拒分。"
            "严重程度：critical。建议立即隔离并更换分闸线圈。")


def _diagnosis_response(role: str) -> str:
    if role == "json":
        return json.dumps({"diagnosis_result": "分闸线圈电阻异常，机械卡涩", "severity": "critical", "related_procedures": "参照断路器拒分故障处理流程（doc_002）"}, ensure_ascii=False)
    return "诊断结论：基于设备数据和故障现象分析，判断为机械操作机构卡涩，需进一步检查分闸线圈和传动部件。"


def _solution_response(role: str) -> str:
    if role == "json":
        return json.dumps({"solution_plan": "1.紧急措施：立即降负荷，通知检修班组15分钟内到场。2.排查步骤：隔离故障设备→测量分闸线圈电阻→检查操动机构→更换故障部件。3.预计修复时间：4-8小时。", "alert_sent": True}, ensure_ascii=False)
    return "处置方案：立即隔离EP-D-002断路器，安排检修班组更换分闸线圈，预计修复时间4-8小时。已发送告警通知。"


def _execute_response(role: str) -> str:
    if role == "json":
        return json.dumps({"execution_record": "巡检记录IR-EP-D-002：断路器拒分故障已记录，处置方案已生成，通知已推送至运维平台。", "status": "completed"}, ensure_ascii=False)
    return "执行记录已生成并推送至运维平台。巡检编号IR-EP-D-002，状态：已完成。"


def _summary_response() -> str:
    return json.dumps({"total_count": 12, "normal_count": 8, "abnormal_count": 4, "by_type": {"变压器": 4, "断路器": 2, "输电线路": 2, "配电柜": 2, "开关柜": 2}, "abnormal_list": ["220kV 天河断路器", "海珠站 10kV 配电柜 B"]}, ensure_ascii=False)


def _analysis_response() -> str:
    return "EP-D-002 220kV天河断路器当前处于异常状态，最近一次巡检日期为2026-07-07，巡检人王工。该设备为西门子制造，SF6灭弧，建议重点关注其操动机构和灭弧室状态。"


def _supervisor_decision(prompt_text: str) -> str:
    """模拟 Supervisor 的调度决策"""
    if "诊断结论" not in prompt_text or "尚未诊断" in prompt_text or 'null' in prompt_text:
        return "diagnosis_agent"
    elif "方案" not in prompt_text or "尚未制定" in prompt_text:
        return "solution_agent"
    elif "执行" not in prompt_text or "尚未执行" in prompt_text:
        return "execute_agent"
    else:
        return "FINISH"


def _default_response(role: str) -> str:
    return f"[离线模拟] 基于输入内容生成的{role}响应。去掉 --offline 参数可使用真实 API。"


# ---------------------------------------------------------------------------
# 模拟 ChatOpenAI（替代真实 LLM 调用）
# ---------------------------------------------------------------------------

class FakeMessage:
    """模拟 langchain_core.messages.AIMessage — 只需要 .content 属性"""

    def __init__(self, content: str):
        self.content = content


class MockChatOpenAI:
    """模拟 ChatOpenAI — 提供相同的 .invoke() 接口，不调用任何外部 API

    工作原理：
      1. 收到 invoke(messages) 调用
      2. 提取最后一条用户消息的文本
      3. 调用 mock_llm_response() 生成模拟响应
      4. 包装为 FakeMessage 返回（.content 属性兼容）

    用途：
      各实验在 --offline 模式下用 MockChatOpenAI 替代 ChatOpenAI，
      代码结构 100% 不变，只是 LLM 响应来自本地模拟而非网络 API。
    """

    def __init__(self, **kwargs):
        # 接受所有 ChatOpenAI 的参数，全部忽略
        pass

    def invoke(self, messages, **kwargs):
        """模拟 LLM 调用 — 等同 ChatOpenAI.invoke() 接口"""
        # 提取最后一条用户消息
        prompt_text = ""
        if isinstance(messages, list):
            for m in reversed(messages):
                if isinstance(m, dict):
                    if m.get("role") in ("user", "human"):
                        prompt_text = m.get("content", "")
                        break
                elif hasattr(m, "content"):
                    prompt_text = str(m.content)
                    break
        elif isinstance(messages, str):
            prompt_text = messages

        response = mock_llm_response(prompt_text)
        return FakeMessage(response)


def make_llm(offline: bool = False, **kwargs):
    """LLM 工厂 — 根据模式返回真实或模拟对象

    用法：
      llm = make_llm(offline=OFFLINE, model="qwen-plus", temperature=0)
      result = llm.invoke("某个问题")  # 两种模式接口一致
    """
    if offline:
        return MockChatOpenAI(**kwargs)
    else:
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        return ChatOpenAI(
            model=kwargs.get("model", "qwen-plus"),
            base_url=base_url,
            api_key=api_key,
            temperature=kwargs.get("temperature", 0),
        )


# ---------------------------------------------------------------------------
# 模拟 Embedding（用于 RAG 实验）
# ---------------------------------------------------------------------------

class MockEmbeddings:
    """模拟 Embedding 模型 — 用文本哈希生成确定性伪向量

    离线模式下 FAISS 仍然可以正常构建索引、执行检索，
    同一文本总是产生同一向量（基于 MD5 哈希），
    所以"语义相同"的文本向量距离也近。
    数据流和代码结构完全真实。
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        vectors = []
        for text in texts:
            h = hashlib.md5(text.encode()).digest()
            vec = [(b / 255.0) for b in h[:16]]
            vec = vec * 8  # 16 * 8 = 128 维
            vectors.append(vec)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def __call__(self, text: str) -> list[float]:
        """让 MockEmbeddings 可以被当作函数调用

        FAISS 内部用 self.embedding_function(text) 调用 embedding，
        而不是 self.embedding_function.embed_query(text)。
        """
        return self.embed_query(text)


def make_embeddings(offline: bool = False, **kwargs):
    """Embedding 工厂"""
    if offline:
        return MockEmbeddings()
    else:
        from langchain_openai import OpenAIEmbeddings
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        return OpenAIEmbeddings(
            model=kwargs.get("model", "text-embedding-v1"),
            base_url=base_url,
            api_key=api_key,
        )
