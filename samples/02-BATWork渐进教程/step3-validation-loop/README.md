# Step 3: + 校验-重试回路

**相比 Step 2 新增**：校验 → 重试 → replan → 兜底 完整回路。

```
understand_intent → enrich_context → plan_tasks ─┬→ execute_tool ⇄ validate_result
                                                   │        │
                                                   │        └→ handle_error（兜底）
                                                   │
                                                   └→ generate_output → END
```

**新增能力**：
- ✅ **结果校验**（validate_result）：检查工具执行是否成功、输出是否非空
- ✅ **重试机制**（retry）：失败后重试当前步骤（最多 2 次）→ 超过则 replan → 再失败则兜底
- ✅ **兜底策略**（handle_error）：用已有部分结果尽力生成降级报告
- ✅ **条件路由**（3 个分叉点）：plan 后 / execute 后 / validate 后

**还不具备**：
- ❌ 无长期记忆（跨会话）
- ❌ 无 Skill 系统
- ❌ 无 Web 界面

**运行**：
```bash
pip install -r requirements.txt
python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b -q "分析 sales.csv 的销售数据"
```
