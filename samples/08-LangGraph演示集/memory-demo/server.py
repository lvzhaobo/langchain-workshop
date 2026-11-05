"""记忆系统 Demo — 四层记忆架构 + 自动晋升 + 跨会话恢复

对应：Day2 模块四 · sample-13 · OpenClaw 四层架构

四层记忆：
  Layer 1: 短期记忆 — MessagesState (add_messages)
  Layer 2: 工作记忆 — State 字段 (当前排查进度)
  Layer 3: 长期记忆 — MEMORY.md (精选事实, LLM 自主写入)
  Layer 4: 语义检索 — 关键词搜索所有记忆文件

新增能力：
  ① Daily Log — 每日自动记录 YYYY-MM-DD.md
  ② 记忆晋升 — LLM 分析 Daily Log, 重要事实提升到 MEMORY.md
  ③ 跨会话恢复 — 新会话自动加载相关记忆注入 System Prompt

启动: python server.py → http://localhost:8400
"""

import os, json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, render_template_string, request, Response
from flask_cors import CORS

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent
MEMORY_MD = BASE_DIR / "MEMORY.md"
PROFILE_MD = BASE_DIR / "PROFILE.md"
DAILY_DIR = BASE_DIR / "memory"
DAILY_DIR.mkdir(exist_ok=True)

TODAY = datetime.now().strftime("%Y-%m-%d")
DAILY_FILE = DAILY_DIR / f"{TODAY}.md"

LLM = ChatOpenAI(model="deepseek-v4-pro", api_key=os.getenv("DEEPSEEK_API_KEY"), base_url=os.getenv("DEEPSEEK_BASE_URL"))

# ═══ 记忆工具（5 个） ═══

@tool
def write_daily_log(fact: str) -> str:
    """① 写入当日 Daily Log（自动记录，LLM 觉得有用的都记）。"""
    ts = datetime.now().strftime("%H:%M")
    entry = f"- {fact} — {ts}\n"
    existing = DAILY_FILE.read_text() if DAILY_FILE.exists() else f"# {TODAY} 日记忆\n\n"
    DAILY_FILE.write_text(existing + entry)
    return f"已记入 Daily Log: {fact}"


@tool
def write_longterm_memory(fact: str, category: str = "general") -> str:
    """② 写入长期记忆 MEMORY.md（精选事实，不轻易使用）。category: identity/preference/project/decision"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [{category}] {fact} — {ts}\n"
    existing = MEMORY_MD.read_text() if MEMORY_MD.exists() else ""
    MEMORY_MD.write_text(existing + entry)
    return f"已写入长期记忆 [{category}]: {fact}"


@tool
def update_profile(field: str, value: str) -> str:
    """③ 更新用户画像。field: name/role/station/device_focus/preference"""
    profile = {}
    if PROFILE_MD.exists():
        for line in PROFILE_MD.read_text().strip().split("\n"):
            if ":" in line: k, v = line.split(":", 1); profile[k.strip()] = v.strip()
    profile[field] = value
    PROFILE_MD.write_text("\n".join(f"{k}: {v}" for k, v in profile.items()))
    return f"画像已更新: {field} = {value}"


@tool
def search_memories(query: str) -> str:
    """④ 搜索所有记忆文件（Daily Log + MEMORY.md + 画像）"""
    results = []
    for f in list(DAILY_DIR.glob("*.md")) + ([MEMORY_MD] if MEMORY_MD.exists() else []) + ([PROFILE_MD] if PROFILE_MD.exists() else []):
        if f.exists():
            text = f.read_text()
            if any(kw in text for kw in query.split()):
                results.append(f"[{f.name}] {text.strip()[:300]}")
    return "\n\n".join(results[-5:]) if results else "未找到相关记忆"


@tool
def promote_memories() -> str:
    """⑤ 晋升：LLM 扫描今日 Daily Log，把重要事实提升到 MEMORY.md（用户身份/偏好/项目背景/重要决策）"""
    if not DAILY_FILE.exists():
        return "今日无 Daily Log，无需晋升"
    daily = DAILY_FILE.read_text()
    # 简化规则：包含关键身份词的行自动晋升
    promoted = 0
    keywords = ["负责", "工作", "站点", "关注", "偏好", "决定", "项目", "设备", "记住"]
    for line in daily.split("\n"):
        if line.startswith("- ") and any(kw in line for kw in keywords):
            write_longterm_memory.invoke({"fact": line[2:].split(" — ")[0], "category": "general"})
            promoted += 1
    return f"晋升完成: 从 Daily Log 提取 {promoted} 条 → MEMORY.md"


TOOLS = [write_daily_log, write_longterm_memory, update_profile, search_memories, promote_memories]
LLM_WITH_TOOLS = LLM.bind_tools(TOOLS)

# ═══ System Prompt — 告诉 LLM 记忆写入规则 ═══

def build_system_prompt() -> str:
    """跨会话恢复：加载所有记忆文件，注入 System Prompt"""
    memory_ctx = ""
    if MEMORY_MD.exists(): memory_ctx += f"## 长期记忆\n{MEMORY_MD.read_text()}\n"
    if PROFILE_MD.exists(): memory_ctx += f"## 用户画像\n{PROFILE_MD.read_text()}\n"
    # 最近 3 天的 Daily Log
    for f in sorted(DAILY_DIR.glob("*.md"))[-3:]:
        memory_ctx += f"\n## {f.stem}\n{f.read_text()[:500]}\n"

    return f"""你是 5G 基站运维助手，拥有四层记忆系统。

{memory_ctx if memory_ctx else "（暂无记忆，新用户）"}

## 记忆写入规则（重要！）
1. 用户透露身份信息（姓名/职位/站点/关注设备）→ 调 write_longterm_memory + update_profile
2. 用户提到项目背景、重要决策 → 调 write_longterm_memory
3. 一般的排查过程、对话内容 → 调 write_daily_log
4. 对话结束时调 promote_memories，晋升 Daily Log 中的关键信息
5. 新会话自动加载上述记忆，无需用户重复告知"""

# ═══ Agent ═══

def agent_node(state: MessagesState) -> dict:
    prompt = build_system_prompt()
    msgs = [SystemMessage(content=prompt)] + state["messages"]
    return {"messages": [LLM_WITH_TOOLS.invoke(msgs)]}

def should_continue(state: MessagesState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "__end__"

builder = StateGraph(MessagesState)
builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": END})
builder.add_edge("tools", "agent")
agent = builder.compile()

# ═══ API ═══

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    q = data.get("question", "")
    tid = data.get("thread_id", "mem-" + str(int(datetime.now().timestamp())))

    def generate():
        config = {"configurable": {"thread_id": tid}}
        for chunk in agent.stream({"messages": [HumanMessage(content=q)]}, config, stream_mode="messages"):
            if isinstance(chunk, tuple) and hasattr(chunk[0], "content") and chunk[0].content:
                yield f"data: {json.dumps({'content': chunk[0].content, 'type': getattr(chunk[0], 'type', 'ai')})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")

@app.route("/memory", methods=["GET"])
def get_memory():
    mem = MEMORY_MD.read_text() if MEMORY_MD.exists() else ""
    prof = PROFILE_MD.read_text() if PROFILE_MD.exists() else ""
    daily = DAILY_FILE.read_text() if DAILY_FILE.exists() else ""
    return jsonify({"memory": mem, "profile": prof, "daily": daily, "daily_file": str(DAILY_FILE)})

@app.route("/memory/promote", methods=["POST"])
def promote():
    result = promote_memories.invoke({})
    return jsonify({"status": "ok", "result": result})

@app.route("/memory/reset", methods=["POST"])
def reset():
    for f in [MEMORY_MD, PROFILE_MD, DAILY_FILE] + list(DAILY_DIR.glob("*.md")):
        if f.exists(): f.write_text("")
    return jsonify({"status": "ok"})

@app.route("/memory/timeline", methods=["GET"])
def timeline():
    entries = []
    for f in sorted(DAILY_DIR.glob("*.md"))[-7:]:
        if f.exists():
            for line in f.read_text().strip().split("\n"):
                if line.startswith("- "):
                    entries.append({"source": f.name, "fact": line[2:], "time": f.stem})
    if MEMORY_MD.exists():
        for line in MEMORY_MD.read_text().strip().split("\n"):
            if line.startswith("- ["):
                entries.append({"source": "MEMORY.md", "fact": line, "time": ""})
    return jsonify({"entries": entries[-30:], "total": len(entries)})

# ═══ HTML — 四层记忆可视化 ═══
HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>四层记忆系统 Demo</title>
<style>
:root{--bg:#f8f9fa;--card:#fff;--text:#1a1a2e;--text2:#6b7280;--text3:#9ca3af;--border:#e5e7eb;--primary:#2563eb;--primary-light:#eff6ff;--green:#059669;--green-bg:#ecfdf5;--amber:#d97706;--amber-bg:#fffbeb;--purple:#7c3aed;--purple-bg:#f5f3ff}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;background:var(--bg);color:var(--text);padding:20px;line-height:1.6}
h1{font-size:20px;margin-bottom:4px}h1 span{font-weight:400;color:var(--text3);font-size:13px}
.subtitle{color:var(--text2);font-size:12px;margin-bottom:16px}
.layout{display:flex;gap:14px;max-width:1300px}.main{flex:1;min-width:0}.side{width:420px;flex-shrink:0;display:flex;flex-direction:column;gap:12px}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px}
.card h3{font-size:13px;margin-bottom:6px;display:flex;align-items:center;gap:6px}
.tag{display:inline-block;padding:2px 6px;border-radius:3px;font-size:9px;font-weight:700}
.tag-l1{background:var(--primary-light);color:var(--primary)}.tag-l2{background:var(--amber-bg);color:var(--amber)}
.tag-l3{background:var(--purple-bg);color:var(--purple)}.tag-l4{background:var(--green-bg);color:var(--green)}
.chat-area{background:var(--card);border:1px solid var(--border);border-radius:10px;display:flex;flex-direction:column;min-height:320px;max-height:500px}
.chat-hd{padding:10px 14px;border-bottom:1px solid var(--border);font-weight:600;font-size:13px}
.chat-body{flex:1;overflow-y:auto;padding:14px;font-size:12px}
.chat-body .msg{margin-bottom:10px;padding:8px 12px;border-radius:8px;max-width:85%}
.chat-body .msg.user{background:var(--primary-light);margin-left:auto}
.chat-body .msg.ai{background:#f3f4f6;margin-right:auto}
.chat-body .msg.tool{background:var(--green-bg);margin-right:auto;font-size:11px;color:var(--green)}
.chat-body .role{font-size:9px;font-weight:700;margin-bottom:2px;text-transform:uppercase}
.chat-input{display:flex;gap:8px;padding:10px 14px;border-top:1px solid var(--border)}
.chat-input input{flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:12px;outline:none}
.chat-input button{padding:8px 14px;border:none;border-radius:6px;background:var(--primary);color:#fff;cursor:pointer;font-size:12px;font-weight:600}
.mem-list{font-size:11px;line-height:1.7;max-height:150px;overflow-y:auto}
.mem-list .entry{padding:2px 0;border-bottom:1px solid #f3f4f6}
.cat{font-size:9px;font-weight:700;padding:1px 5px;border-radius:2px;margin-right:4px}
.cat-identity{background:#eff6ff;color:#2563eb}.cat-preference{background:#fef3c7;color:#92400e}
.cat-project{background:#f3e8ff;color:#7c3aed}.cat-dec{background:#fef2f2;color:#dc2626}.cat-general{background:#f3f4f6;color:#6b7280}
.btn-sm{padding:3px 8px;border:1px solid var(--border);border-radius:4px;background:#fff;cursor:pointer;font-size:10px;color:var(--text2)}
.timeline{font-size:10px;line-height:1.7;max-height:120px;overflow-y:auto;color:var(--text2)}
</style></head><body>
<h1>四层记忆系统 Demo <span>— Daily Log + 自动晋升 + 跨会话恢复</span></h1>
<p class="subtitle">对应 Day2 模块四 · sample-13 · OpenClaw 四层架构</p>

<div class="layout">
<div class="main">
  <div class="chat-area">
    <div class="chat-hd">对话窗口 <span style="font-weight:400;color:var(--text3);font-size:11px">（Layer 1 短期记忆 + Layer 2 工作记忆）</span></div>
    <div class="chat-body" id="chatBody">
      <div style="color:var(--text3);text-align:center;padding:40px">告诉我你是谁、负责哪个站点。Agent 会自动写入 Daily Log 和长期记忆。</div>
    </div>
    <div class="chat-input">
      <input id="question" placeholder="试试：我叫张三，在望京SOHO负责AAU运维…" onkeydown="if(event.key==='Enter')send()">
      <button onclick="send()">发送</button>
    </div>
  </div>
</div>

<div class="side">
  <div class="card">
    <h3><span class="tag tag-l1">Layer 1-2</span> 短期 + 工作记忆 <span style="font-weight:400;color:var(--text3);font-size:10px">当前对话 · 自动管理</span></h3>
    <div style="font-size:11px;color:var(--text2)">MessagesState + add_messages 自动追加<br>State 字段记录排查进度</div>
  </div>
  <div class="card">
    <h3><span class="tag tag-l2">Daily Log</span> 每日记录 <button class="btn-sm" onclick="promoteMem()" style="margin-left:auto">晋升</button></h3>
    <div class="mem-list" id="dailyList"><span style="color:var(--text3)">加载中…</span></div>
  </div>
  <div class="card">
    <h3><span class="tag tag-l3">Layer 3</span> 长期记忆 MEMORY.md <button class="btn-sm" onclick="loadMemory()">刷新</button></h3>
    <div class="mem-list" id="memList"><span style="color:var(--text3)">加载中…</span></div>
  </div>
  <div class="card">
    <h3><span class="tag tag-l4">Layer 4</span> 语义检索 · 跨会话恢复</h3>
    <div style="font-size:11px;color:var(--text2)">新会话 → 自动加载 Daily Log (3天) + MEMORY.md + 画像 → 注入 Prompt</div>
  </div>
  <div class="card">
    <h3>记忆时间线</h3>
    <div class="timeline" id="timelineLine"><span style="color:var(--text3)">加载中…</span></div>
    <button class="btn-sm" onclick="resetAll()" style="margin-top:4px;color:var(--danger)">重置全部记忆</button>
  </div>
</div>
</div>

<script>
var currentAIDiv = null;
async function send(){
  var q=document.getElementById('question').value.trim();if(!q)return;
  document.getElementById('question').value='';
  var body=document.getElementById('chatBody');
  body.innerHTML+='<div class="msg user"><div class="role">用户</div>'+q+'</div>';
  var aiId='ai'+Date.now();body.innerHTML+='<div class="msg ai" id="'+aiId+'"><div class="role">Agent</div></div>';
  body.scrollTop=body.scrollHeight;var out=document.getElementById(aiId);
  var r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,thread_id:'mem-'+Date.now()})});
  var reader=r.body.getReader();var dec=new TextDecoder();
  while(true){var rr=await reader.read();if(rr.done)break;
    for(var line of dec.decode(rr.value).split('\\n')){
      if(!line.startsWith('data: '))continue;var p=line.slice(6);if(p==='[DONE]')continue;
      try{var d=JSON.parse(p);if(d.type==='tool'){body.innerHTML+='<div class="msg tool">'+d.content+'</div>';aiId='ai'+Date.now();body.innerHTML+='<div class="msg ai" id="'+aiId+'"><div class="role">Agent</div></div>';out=document.getElementById(aiId)}else{out.textContent+=d.content}}catch(e){}
    }body.scrollTop=body.scrollHeight;
  }loadAll();
}
async function loadAll(){
  var r=await fetch('/memory');var d=await r.json();
  document.getElementById('memList').innerHTML = d.memory.split('\\n').filter(function(l){return l.trim()}).map(function(l){var cat='general';if(l.includes('[identity]'))cat='identity';else if(l.includes('[preference]'))cat='preference';else if(l.includes('[project]'))cat='project';return '<div class="entry"><span class="cat cat-'+cat+'">'+cat+'</span>'+l.replace(/\\[.*?\\] /,'')+'</div>'}).join('')||'（空）';
  document.getElementById('dailyList').innerHTML = d.daily.split('\\n').filter(function(l){return l.startsWith('- ')}).slice(-10).map(function(l){return '<div class="entry">'+l.substring(2)+'</div>'}).join('')||'（空）';
  var tr=await fetch('/memory/timeline');var td=await tr.json();
  document.getElementById('timelineLine').innerHTML = td.entries.slice(-15).reverse().map(function(e){return '<div>'+e.source+' '+e.fact.substring(0,60)+'</div>'}).join('')||'（空）';
}
async function promoteMem(){await fetch('/memory/promote',{method:'POST'});loadAll();}
async function resetAll(){await fetch('/memory/reset',{method:'POST'});loadAll();}
loadAll();
</script></body></html>"""

if __name__ == "__main__":
    print("四层记忆系统 Demo: http://localhost:8400")
    app.run(host="0.0.0.0", port=8400, debug=False)
