"""Text-to-SQL — 自然语言查询设备数据库

运行：python text_to_sql.py
依赖：pip install langchain langchain-openai
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))  # 自动读取课程根目录 .env

import json
import sqlite3
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain.agents import tool, create_react_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate

# ═══ 配置 ═══
API_KEY = os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY")
API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")
DEVICES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "devices.json")

# 数据库连接（模块级变量，init_db 后赋值）
db_conn: sqlite3.Connection = None

SCHEMA = """
表 devices:
  device_id(TEXT 主键), model(TEXT 型号), vendor(TEXT 厂商),
  site(TEXT 站点), type(TEXT 类型), status(TEXT 状态),
  ip(TEXT), online_date(TEXT)
  status: running/alarm/maintenance

表 alarms:
  alarm_id(TEXT 主键), device_id(TEXT 外键),
  type(TEXT 告警类型), severity(TEXT 级别),
  time(TEXT), description(TEXT)
  severity: P0/P1/P2/P3

关联: alarms.device_id → devices.device_id
"""


# ═══ 数据库初始化 ═══
def init_db(devices_file=DEVICES_FILE) -> sqlite3.Connection:
    """把 devices.json 导入 SQLite 内存数据库"""
    global db_conn

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE devices (
            device_id TEXT PRIMARY KEY,
            model TEXT,
            vendor TEXT,
            site TEXT,
            type TEXT,
            status TEXT,
            ip TEXT,
            online_date TEXT
        );
        CREATE TABLE alarms (
            alarm_id TEXT PRIMARY KEY,
            device_id TEXT,
            type TEXT,
            severity TEXT,
            time TEXT,
            description TEXT,
            FOREIGN KEY (device_id) REFERENCES devices(device_id)
        );
    """)

    # 导入数据
    devices_path = Path(__file__).parent / devices_file
    with open(devices_path, encoding="utf-8") as f:
        devices = json.load(f)

    device_count = 0
    alarm_count = 0
    for d in devices:
        conn.execute(
            """INSERT INTO devices
               (device_id, model, vendor, site, type, status, ip, online_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (d["device_id"], d["model"], d["vendor"], d["site"],
             d["type"], d["status"], d["ip"], d["online_date"])
        )
        device_count += 1

        for a in d.get("alarms", []):
            try:
                conn.execute(
                    """INSERT INTO alarms
                       (alarm_id, device_id, type, severity, time, description)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (a["alarm_id"], d["device_id"], a["type"],
                     a["severity"], a["time"], a["description"])
                )
                alarm_count += 1
            except sqlite3.IntegrityError:
                pass  # 重复的 alarm_id 跳过

    conn.commit()
    db_conn = conn
    print(f"数据库初始化完成：{device_count} 台设备，{alarm_count} 条告警")
    return conn


# ═══ 工具定义 ═══
_sql_llm = None  # 延迟初始化


def _get_sql_llm():
    global _sql_llm
    if _sql_llm is None:
        _sql_llm = ChatOpenAI(
            model=MODEL,
            temperature=0,
            api_key=API_KEY,
            base_url=API_BASE,
        )
    return _sql_llm


@tool
def query_devices_sql(question: str) -> str:
    """用自然语言查询设备数据库。当用户问统计/分组/筛选类问题时使用。
    例如："告警设备有几台？""华为设备中 running 的占比？"
    "P0 告警最多的站点？"
    """
    llm = _get_sql_llm()

    sql_prompt = f"""你是 SQL 专家。根据表结构和用户问题，生成一条 SQLite SELECT 语句。
只输出 SQL，一行，不要 markdown 格式，不要解释。

表结构：
{SCHEMA}

用户问题：{question}

SELECT"""
    try:
        response = llm.invoke(sql_prompt)
        sql = response.content.strip()

        # 清理格式
        if sql.upper().startswith("SELECT"):
            sql = "SELECT" + sql[6:] if sql[:6] == "SELECT" else sql
        else:
            sql = "SELECT " + sql

        for prefix in ["```sql", "```"]:
            if prefix in sql:
                sql = sql.split(prefix)[1].split("```")[0].strip()
        sql = sql.replace("\n", " ").strip()

        # 安全检查
        dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "EXEC"]
        sql_upper = sql.upper()
        for keyword in dangerous:
            if keyword in sql_upper:
                return f"安全拦截：不允许 {keyword} 操作。只支持 SELECT 查询。"

        # 执行
        cursor = db_conn.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        if not rows:
            # 可能数据值不对，给出提示
            return (
                f"查询成功，但没有匹配的数据。\n"
                f"SQL: {sql}\n"
                f"提示：vendor 包括 华为/中兴/爱立信/诺基亚；"
                f"status 包括 running/alarm/maintenance；"
                f"severity 包括 P0/P1/P2/P3"
            )

        lines = [f"SQL: {sql}", f"结果（{len(rows)} 行）："]

        for row in rows[:20]:
            if columns:
                parts = [f"{col}={row[col]}" for col in columns]
            else:
                parts = [str(val) for val in row]
            lines.append("  " + " | ".join(parts))

        if len(rows) > 20:
            lines.append(f"  ... 还有 {len(rows) - 20} 行")

        return "\n".join(lines)

    except sqlite3.OperationalError as e:
        return f"SQL 执行失败：{e}\n生成的 SQL：{sql if 'sql' in dir() else '无'}"
    except Exception as e:
        return f"查询出错：{e}"


# ═══ 创建 Agent ═══
def make_sql_agent():
    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        api_key=API_KEY,
        base_url=API_BASE,
    )

    tools = [query_devices_sql]

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是 5G 基站数据分析助手。用 query_devices_sql 工具回答统计/筛选类问题。

限制：
- 只查询，不修改数据
- 不确定时先查数据再回答，不要猜测
- 结果为空时如实告知

可用工具：{tools}
工具名称：{tool_names}

格式：
Question: 用户问题
Thought: 分析需要什么数据
Action: query_devices_sql
Action Input: 自然语言描述查询需求
Observation: SQL 查询结果
...（可重复）
Final Answer: 基于数据回答用户问题"""),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_react_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent, tools=tools, verbose=True,
        max_iterations=8, handle_parsing_errors=True,
    )


# ═══ 主程序 ═══
if __name__ == "__main__":
    # 1) 初始化数据库
    print("=" * 60)
    init_db()

    # 2) 确认数据已加载
    print(f"  设备总数: {db_conn.execute('SELECT COUNT(*) FROM devices').fetchone()[0]}")
    print(f"  告警总数: {db_conn.execute('SELECT COUNT(*) FROM alarms').fetchone()[0]}")

    # 3) 创建 Agent
    executor = make_sql_agent()

    # 4) 测试查询
    TEST_QUERIES = [
        "告警设备有多少台？按厂商分组统计",
        "P0 级别告警有几条？分别是什么类型？",
        "华为设备中状态为 running 的有多少？",
        "哪个站点的告警设备最多？列出前 3 名",
        "爱立信设备中，告警最多的型号是什么？",
    ]

    print(f"\n{'='*60}")
    print("Text-to-SQL 查询测试")
    print(f"{'='*60}")

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n{'-'*40}")
        print(f"[{i}/{len(TEST_QUERIES)}] 用户问：{query}")
        try:
            result = executor.invoke({"input": query})
            answer = result["output"]
            print(f"\nAgent 回答：\n{answer[:300]}")
            if len(answer) > 300:
                print(f"  ... (共 {len(answer)} 字符)")
        except Exception as e:
            print(f"❌ 失败：{e}")

    # 5) 快速查数据库直接验证
    print(f"\n{'='*60}")
    print("数据库直接查询验证（对比 Agent 回答的准确性）")
    print(f"{'='*60}")

    verifications = [
        ("厂商分布",
         "SELECT vendor, COUNT(*) as cnt FROM devices GROUP BY vendor"),
        ("告警级别分布",
         "SELECT severity, COUNT(*) as cnt FROM alarms GROUP BY severity"),
        ("站点告警数 Top 3",
         "SELECT site, COUNT(*) as cnt FROM devices WHERE status='alarm' GROUP BY site ORDER BY cnt DESC LIMIT 3"),
    ]

    for label, sql in verifications:
        rows = db_conn.execute(sql).fetchall()
        print(f"\n{label}:")
        for row in rows:
            print(f"  {dict(row)}")

    print(f"\n{'='*60}")
    print("完成！如果 Agent 回答与上述验证结果一致，则 NL→SQL 链路正确。")
