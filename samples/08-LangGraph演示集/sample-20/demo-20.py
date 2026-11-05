"""
sample-20：DeepAgents — "电池全装上"的 Agent 脚手架

运行: python3.13 demo-20.py

对比 sample-6（@tool）、sample-17（MCP）、sample-18（A2A）：
  之前：自己拼 LangGraph State/Node/Edge + @tool + 手动 Memory
  现在：DeepAgents 出厂自带：子系统、文件系统、技能、记忆、规划、HITL、Shell 沙箱

DeepAgents vs LangGraph：
  ┌─────────────────────────────────────────────────┐
  │ DeepAgents                                      │
  │  ┌─────────────────────────────────────────┐    │
  │  │  LangChain create_agent                 │    │
  │  │   ┌─────────────────────────────────┐   │    │
  │  │   │  LangGraph（图运行时 + State）    │   │    │
  │  │   └─────────────────────────────────┘   │    │
  │  └─────────────────────────────────────────┘    │
  └─────────────────────────────────────────────────┘

DeepAgents 出厂配置一览：
  ├── 子系统（Sub-agents）    隔离上下文窗口的专职 Agent
  ├── 文件系统（Filesystem）  读写虚拟/本地/S3 文件
  ├── 技能（Skills）         按需加载 SKILL.md（渐进式披露）
  ├── 记忆（Memory）         跨会话持久化（LangGraph Store）
  ├── 上下文管理              自动摘要 + 长输出卸载到磁盘
  ├── 规划（Planning Tool）   多步任务自动规划
  ├── HITL（人机协同）        工具执行前可审批
  ├── Shell 沙箱              安全执行命令
  └── MCP 兼容              可接入任何 MCP Server
"""

import os, sys

print("=" * 65)
print("sample-20：DeepAgents — 电池全装上的 Agent 脚手架")
print("=" * 65)

# ═══════════════════════════════════════════════════════════
# 1. 安装方式
# ═══════════════════════════════════════════════════════════
print("""
📦 安装 DeepAgents：

    # Python（核心库）
    uv add deepagents
    # 或
    pip install deepagents

    # Deep Agents Code（终端编程 Agent，类似 Claude Code）
    curl -LsSf https://langch.in/dcode | bash

    # 验证
    deepagents --help         # Python 库
    dcode --help              # 终端编程 Agent
""")

# ═══════════════════════════════════════════════════════════
# 2. 最简示例：create_deep_agent
# ═══════════════════════════════════════════════════════════
print("-" * 65)
print("2. 最简示例：create_deep_agent（概念代码，需安装 deepagents 包）")
print("-" * 65)
print("""
    from deepagents import create_deep_agent

    agent = create_deep_agent(
        model="anthropic:claude-sonnet-4-20250514",
        tools=[],                                   # 自定义工具
        system_prompt="你是 5G 网络运维专家。",
    )

    result = agent.invoke({
        "messages": "查 DEV-0001 的状态，写一份运维报告。"
    })
    # → Agent 自动：规划 → 调用工具 → 写报告到文件 → 返回结果

    # 一行代码拿到的东西：
    #   ✅ 自动规划（Planning Tool）
    #   ✅ 上下文管理（长对话自动摘要）
    #   ✅ 文件系统（可写报告到磁盘）
    #   ✅ 长工具输出自动卸载（不会撑爆 context window）
""")

# ═══════════════════════════════════════════════════════════
# 3. Skills 集成示例
# ═══════════════════════════════════════════════════════════
print("-" * 65)
print("3. Skills 集成：用 SKILL.md 注入领域知识")
print("-" * 65)

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")
print(f"   Skills 目录：{SKILLS_DIR}")
print(f"""
    from deepagents import create_deep_agent
    from deepagents.middleware import SkillsMiddleware

    agent = create_deep_agent(
        model="anthropic:claude-sonnet-4-20250514",
        middleware=[
            SkillsMiddleware(skills_dir="{SKILLS_DIR}"),
        ],
    )

    # SkillsMiddleware 做的事：
    #   1. 扫描 skills/ 目录下所有 SKILL.md
    #   2. 只读 YAML frontmatter（name + description）
    #   3. 注入 System Prompt（~5 tokens/skill）
    #   4. Agent 需要时 → 调用 read_file 加载完整 SKILL.md
    #   5. 按照 Skill 里的 SOP 执行任务
""")

# 列出当前 skills 目录中的技能
for skill_dir in sorted(os.listdir(SKILLS_DIR)):
    skill_path = os.path.join(SKILLS_DIR, skill_dir)
    if os.path.isdir(skill_path):
        md_path = os.path.join(skill_path, "SKILL.md")
        if os.path.exists(md_path):
            with open(md_path) as f:
                first_line = f.readline().strip("# \n")
            print(f"   📄 {skill_dir}/SKILL.md — {first_line}")

# ═══════════════════════════════════════════════════════════
# 4. 文件系统 Backend 示例
# ═══════════════════════════════════════════════════════════
print("""
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
4. 文件系统 Backend：多存储层
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    from deepagents.backends import CompositeBackend
    from deepagents.backends.filesystem import LocalFilesystemBackend

    # 复合 Backend：不同路径走不同存储
    fs = CompositeBackend({
        "/workspace/": LocalFilesystemBackend(root_dir="./workspace"),
        "/memories/":  S3FilesystemBackend(bucket="agent-memory"),  # 长期记忆存 S3
    })

    agent = create_deep_agent(
        model="...",
        backend=fs,
    )
    # Agent 写 /workspace/report.md → 本地磁盘
    # Agent 写 /memories/session-42.json → S3（跨会话持久化）
""")

# ═══════════════════════════════════════════════════════════
# 5. MCP 兼容：同时用 Skill + MCP
# ═══════════════════════════════════════════════════════════
print("""
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
5. MCP 兼容：Skill 编排流程，MCP 取实时数据
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    from langchain_mcp_adapters import MultiServerMCPClient

    # MCP 工具：连接外部系统
    mcp = MultiServerMCPClient({
        "5g-devices": {"transport": "stdio",
                       "command": "python3.13 mcp_server.py"},
    })
    mcp_tools = await mcp.get_tools()

    # Skill：注入操作规范
    # skills/5g-diagnose/SKILL.md

    agent = create_deep_agent(
        model="anthropic:claude-sonnet-4-20250514",
        tools=mcp_tools,                              # MCP = 手（取数据）
        middleware=[SkillsMiddleware(skills_dir="skills")],  # Skill = 脑（流程）
    )

    # MCP 做的事：连 5G 设备 → 查状态 → 返回数据
    # Skill 做的事："诊断 5G 告警三步法"、"报告模板"、"安全红线"
""")

# ═══════════════════════════════════════════════════════════
# 6. HITL 人机协同
# ═══════════════════════════════════════════════════════════
print("""
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
6. HITL：工具执行前人工审批
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    agent = create_deep_agent(
        model="...",
        tools=[dangerous_tool],
        interrupt_on={"dangerous_tool": True},  # ← 这行就够
    )
    # Agent 调用 dangerous_tool 时自动暂停，等待人工批准
""")

# ═══════════════════════════════════════════════════════════
# 7. 总结对比
# ═══════════════════════════════════════════════════════════
print("=" * 65)
print("7. 你的 sample 系列在 LangChain 生态中的位置")
print("=" * 65)
print("""
  sample-6   @tool 装饰器        ← 手动绑定工具
  sample-12  Supervisor          ← 一个图内调度多 Agent
  sample-17  MCP                 ← 标准化工具连接协议
  sample-18  A2A                 ← 跨系统 Agent 通信协议
  sample-20  DeepAgents          ← 继承上面所有，加 Skill/记忆/规划/HITL

  层次关系：
  ┌────────────────────────────────────────┐
  │        DeepAgents（出厂配置）            │
  │  ┌──────────────────────────────────┐  │
  │  │  SkillsMiddleware（流程/知识注入） │  │
  │  ├──────────────────────────────────┤  │
  │  │  LangChain create_agent          │  │
  │  │  ├── MCP Tools（连外部系统）       │  │
  │  │  ├── @tool（自定义函数）           │  │
  │  │  ├── A2A Client（调其他 Agent）    │  │
  │  ├──────────────────────────────────┤  │
  │  │  LangGraph（State + Node + Edge） │  │
  │  └──────────────────────────────────┘  │
  └────────────────────────────────────────┘
""")

print("✅ sample-20 完成")
print("   学习路径：sample-6 → sample-17 → sample-18 → sample-20")
print("   安装 deepagents：pip install deepagents")
print("   安装 Deep Agents Code：curl -LsSf https://langch.in/dcode | bash")
