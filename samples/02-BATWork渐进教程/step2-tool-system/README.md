# Step 2: + 工具系统

**相比 Step 1 新增**：工具注册表 + 任务规划 + 工具执行，Agent 从"只能聊天"升级为"能操作文件"。

```
understand_intent → enrich_context → plan_tasks ─┬→ execute_tool（循环）
                                                   │
                                                   └→ generate_output → END
```

**新增能力**：
- ✅ **工具注册表**（[tools.py](tools.py)）：`@register` 装饰器，6 个工具
  - `list_files` — 列出工作目录文件
  - `read_file` — 读取文件内容（CSV/JSON/TXT/MD/PY）
  - `write_file` — 写入文件
  - `analyze_csv` — CSV 统计分析（分组聚合）
  - `run_python` — 执行 Python 代码
  - `generate_report` — 汇总生成 Markdown 报告
- ✅ **任务规划**（plan_tasks）：LLM 把用户需求拆解为 JSON 步骤列表
- ✅ **工具执行**（execute_tool）：按步骤调用工具，结果存入 `tool_results`

**还不具备**：
- ❌ 无校验重试（工具失败 = 直接放弃）
- ❌ 无长期记忆
- ❌ 无 Web 界面

**运行**：
```bash
pip install -r requirements.txt
python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b -q "列出当前目录的文件"
```
