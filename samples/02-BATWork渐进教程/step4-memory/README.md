# Step 4: + Memory 记忆系统

**相比 Step 3 新增**：Agent 拥有长期记忆，跨会话记住历史对话和项目知识。

```
上下文补齐（增强版）:
  enrich_context:
    1. 扫描工作区文件 ✅ (Step 1)
    2. 列出可用工具 ✅ (Step 2)
    3. 🆕 检索历史记忆（ChromaDB 向量 + SQLite 摘要）
    4. 🆕 加载项目知识库（约定/规范/偏好）
```

**新增能力**：
- ✅ **ChromaDB 向量存储**：语义检索历史对话
- ✅ **SQLite 摘要存储**：关键词兜底，离线可用
- ✅ **项目知识库**：持久化项目约定、命名规范、偏好设置
- ✅ **自动记忆保存**：每次 Agent 执行完毕自动存档

**还不具备**：
- ❌ 无 Skill 系统
- ❌ 无 Web 界面

**运行**：
```bash
pip install -r requirements.txt chromadb
python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b -q "和上次一样，再分析一次销售数据"
```
