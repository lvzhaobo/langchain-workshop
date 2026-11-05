# Labs 索引

**26 个并列编号，`01`–`26`。一个目录一个实验，互不依赖。**

## 现状

| 段 | 状态 | 说明 |
|---|---|---|
| **01–03** | ✅ 可跑 | 离线、零 Key、有 `check.py` |
| **05 10** | 🟡 **零 Key 可跑** | 有 `_mock_llm.py`，不配 Key 也能看到完整输出 |
| **04 06–09 11–26** | ⬜ 需配 Key | 配好 `.env` 即可运行；其中 11 个也可按 [零 Key 模式](../docs/零Key模式.md) 改造 |

`./verify.sh` 会给出三态计数：`✅ N 通过  ⬜ M 未接入  ❌ K 失败`。

## 能力分布

| 段 | 内容 |
|---|---|
| `01–03` | LangGraph 骨架：State / 工具循环 / Checkpointer |
| `04` `15` | **低代码平台对照**（Dify） |
| `05–11` | LangChain 零件：Agent / Prompt / Tool / Parser / Agent 对比 / RunnableBranch / LCEL |
| `12–15` | 检索与 RAG：FAISS / 余弦相似度 / RAG Agent / Dify RAG |
| `16–20` | 单 Agent 全栈：Memory / Callbacks / Caching / RAG 评测 / Text-to-SQL |
| `21–26` | 多 Agent 与生产化：意图路由 / 多 Agent / 协作模式 / HITL / 可观测 / LLM 裁判 |

## 低代码平台对照（2 个）

`04-DifyAgent`、`15-Dify-RAG-Agent` 用的是 **Dify**，不在 LangChain 代码栈里。
保留原因：让学员看到"另一条路"长什么样。**验收物是导出的 DSL / 应用配置，不是 `.py`。**

## 一个已适配 lab 的结构

```
NN-xxx/
├── README.md      # 目标 / 时长 / 步骤 / 验收 / 卡住了
├── main.py        # 你的代码，带 # TODO
├── solution.py    # 参考答案
└── check.py       # 验收脚本
```

## 硬约束

| 约束 | 值 |
|---|---|
| 时长 | 15–30 分钟，超过就拆 |
| 骨架行数 | < 100 行 |
| 外部依赖 | 零（不联网、不需 Key） |
| 必须有 | `solution.py` + `check.py` |
| 禁止 | **import 别的 lab，或读别的 lab 的目录** |

## 新增一个 lab

1. `cp -r labs/_template labs/NN-你的主题`
2. 改 `README.md` 四段（目标 / 步骤 / 验收 / 卡住了）
3. 写 `solution.py`，再**反着写** `main.py`（关键几行换成 `# TODO`）
4. 写 `check.py`：`python check.py` 对骨架**失败**，`--solution` 对答案**通过**
5. `./verify.sh` 确认三态计数符合预期
