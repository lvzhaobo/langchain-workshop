# Step 5: + Skill 系统

**相比 Step 4 新增**：用户通过写 Markdown 文件"教"Agent 新能力，不必改代码。

```
上下文补齐（增强版）:
  enrich_context:
    1. 扫描工作区文件 ✅ (Step 1)
    2. 列出可用工具 ✅ (Step 2)
    3. 检索历史记忆 ✅ (Step 4)
    4. 加载项目知识库 ✅ (Step 4)
    5. 🆕 扫描 Skills 目录 → 匹配触发条件 → 注入执行提示

skills/
  └── example-skill/
      └── SKILL.md     ← 用户手写，声明式定义新能力
```

**新增能力**：
- ✅ **SKILL.md 解析器**（[skill_loader.py](skill_loader.py)）：自动扫描 `skills/` 目录
- ✅ **触发条件匹配**：用户输入命中 Skill 的触发词时自动激活
- ✅ **声明式技能定义**：触发条件 / 执行步骤 / 约束 三段式结构
- ✅ **示例 Skill**：月度经营分析报告

**还不具备**：
- ❌ 无 Web 界面

**运行**：
```bash
pip install -r requirements.txt chromadb
python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b -q "帮我生成一份月度经营分析报告"
```
