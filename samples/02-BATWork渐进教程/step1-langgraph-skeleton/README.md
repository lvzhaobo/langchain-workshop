# Step 1: 基础 Agent Loop

**新增内容**：LangGraph 3 节点直线拓扑——Agent 的最简骨架。

```
user_input → understand_intent → enrich_context → generate_output → END
```

**新增能力**：
- ✅ 意图理解：LLM 提炼用户需求
- ✅ 上下文补齐：扫描工作目录文件
- ✅ 产物生成：LLM 汇总生成 Markdown 报告

**还不具备**：
- ❌ 无工具调用（Agent 只能"聊"，不能操作文件）
- ❌ 无任务规划（不会拆解复杂任务）
- ❌ 无校验重试（一次失败就结束）

**运行**：
```bash
pip install -r requirements.txt
python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b -q "你好"
```
