"""Langfuse Trace — 一行接入多 Agent 流水线的可观测面板

前置条件：
    pip install langfuse langchain langchain-openai
    docker compose up -d  # 启动 Langfuse → http://localhost:3000

对比 trace_demo.py：
    trace_demo.py — 纯 Python 本地收集（零依赖、零注册）
    本文件        — Langfuse 自托管（自动采集、Web 可视化、持久化）

运行：python trace_langfuse.py
"""
import os

# ══════════════════════════════════════════════════════════════
# 配置：从环境变量或 .env 读取
# ══════════════════════════════════════════════════════════════

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-...")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-...")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

# 控制开关：如果没配密钥 → 降级到本地 Tracer，不报错
LANGFUSE_ENABLED = (
    LANGFUSE_PUBLIC_KEY not in ("", "pk-lf-...")
    and LANGFUSE_SECRET_KEY not in ("", "sk-lf-...")
)


# ══════════════════════════════════════════════════════════════
# 策略：Langfuse 优先，降级到本地 Tracer
# ══════════════════════════════════════════════════════════════

class SmartTracer:
    """
    自动选择 Tracer：
    - 如果 LANGFUSE 密钥配置了 → 用 Langfuse CallbackHandler
    - 否则 → 降级到 trace_demo.py 的 LocalTracer（零依赖可用）

    这样同一个实验文件，学员配不配密钥都能跑。
    """

    def __init__(self):
        self._handler = None
        self._local_tracer = None
        self._mode = "local"

        if LANGFUSE_ENABLED:
            try:
                from langfuse.langchain import CallbackHandler
                self._handler = CallbackHandler(
                    public_key=LANGFUSE_PUBLIC_KEY,
                    secret_key=LANGFUSE_SECRET_KEY,
                    host=LANGFUSE_HOST,
                )
                self._mode = "langfuse"
                print(f"Langfuse 已连接: {LANGFUSE_HOST}")
            except ImportError:
                print("langfuse 未安装，降级到本地 Tracer")
                print("   pip install langfuse 后重试")
            except Exception as e:
                print(f"Langfuse 连接失败: {e}")
                print("   降级到本地 Tracer")
        else:
            print("未配置 LANGFUSE 密钥，使用本地 Tracer")

        # 本地 Tracer 作为兜底
        if self._mode == "local":
            from trace_demo import LocalTracer
            self._local_tracer = LocalTracer()

    def get_callback(self):
        """返回 LangChain 可用的 callback 配置"""
        if self._mode == "langfuse":
            return {"callbacks": [self._handler]}
        return {}

    def start_trace(self, name: str, input_data: dict = None):
        if self._local_tracer:
            self._local_tracer.start_trace(name, input_data)

    def end_trace(self):
        if self._local_tracer:
            return self._local_tracer.end_trace()

    def start_span(self, name: str, span_type: str = "agent"):
        if self._local_tracer:
            self._local_tracer.start_span(name, span_type)

    def end_span(self, output: dict = None, tokens: int = 0):
        if self._local_tracer:
            self._local_tracer.end_span(output, tokens)

    def flush(self):
        """Langfuse 模式下确保数据上报完成"""
        if self._handler:
            self._handler.flush()

    @property
    def mode(self):
        return self._mode


# ══════════════════════════════════════════════════════════════
# 演示：和 trace_demo.py 同一套流水线，但数据上 Langfuse
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from trace_demo import (
        simulate_detector,
        simulate_diagnoser,
        simulate_decider,
        simulate_executor,
    )

    print("实验 3.6（进阶）：Langfuse Trace — 生产级可观测面板")
    print("=" * 60)

    tracer = SmartTracer()
    print(f"当前模式: {tracer.mode}\n")

    # ── 同一套排障流水线 ──
    device_id = "DEV-0001"
    tracer.start_trace(f"排障流水线-{device_id}", {"device_id": device_id})

    simulate_detector(tracer, device_id)
    simulate_diagnoser(tracer, device_id)
    simulate_decider(tracer)
    simulate_executor(tracer)

    trace = tracer.end_trace()
    if trace:
        total_ms = trace.get("total_elapsed_ms", 0)
        total_tokens = trace.get("total_tokens", 0)
        print(f"\n   总耗时: {total_ms}ms | 总 Token: {total_tokens}")

    tracer.flush()

    # ── 指引 ──
    if tracer.mode == "langfuse":
        print(f"""
{"="*60}
打开 Langfuse Dashboard 查看 Trace
   → {LANGFUSE_HOST}

   1. Traces 页面 → 找到 "排障流水线-DEV-0001"
   2. 点进去 → 看到 4 个 Span（detector / diagnoser / decider / executor）
   3. 每个 Span 的耗时柱状图 + 输入输出

   对比 trace_demo.py 的控制台输出：
   - 本地：手动写 start_span/end_span，查看用 print
   - Langfuse：Callback 自动采集，Web 面板搜索+聚合+导出
{"="*60}
""")
    else:
        print(f"""
{"="*60}
ℹ  当前为本地 Tracer 模式。开启 Langfuse：

   1. docker compose up -d  # 启动服务
   2. 打开 http://localhost:3000 → Settings → API Keys → 创建密钥
   3. 设置环境变量：
      export LANGFUSE_PUBLIC_KEY=pk-lf-你的公钥
      export LANGFUSE_SECRET_KEY=sk-lf-你的私钥
      export LANGFUSE_HOST=http://localhost:3000
   4. 重新运行: python trace_langfuse.py
{"="*60}
""")
