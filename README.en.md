# LangChain Workshop

**English** · [中文](README.md)

> **Hands-on labs for the whole LangChain family — LangChain, LangGraph, LangSmith, LangServe.**
> Code-first, no low-code platforms.

28 labs, 8 full projects, 6,000+ lines of Chinese documentation.
**21 of the 28 labs run with zero API keys** — no network, no credentials, no cost.

```bash
./setup.sh      # create .venv (Python 3.11) and install deps
./run.sh 01     # run Lab 01
./verify.sh     # run all automated checks (no keys needed)
```

---

## Why `langchain` and not `langgraph`

`LangGraph`, `LangSmith` and `LangServe` all live under the **`langchain-ai`** org, and
`langgraph` depends on `langchain-core`. **LangChain is the family; LangGraph is one package in it.**

Naming the repo `langgraph` would be naming the whole stack after one of its parts.

**Versus Dify / Coze**: the difference isn't whether they can build agents — it's **who writes the logic**.

| | What you write | Examples |
|---|---|---|
| **Code stack** (this repo) | `.py` files | LangChain / LangGraph / LangSmith / LangServe |
| Low-code platforms | DSL / app config JSON | Dify / Coze / n8n |

---

## What's inside

| Directory | What it is |
|---|---|
| **`labs/`** | 28 self-contained experiments, 15–30 min each. **You write the code.** |
| **`samples/`** | 8 complete projects. **You read the code.** Used for instructor demos. |
| **`docs/`** | 39 documents: fundamentals, cheat sheets, setup, model configuration. |

Each lab ships with a `check.py` that asserts the output — so "does it work?" is answered
by a script, not by eyeballing.

---

## Zero-key mode

Most tutorial repos break at step four because you need an API key. This one doesn't:

```
$ ./run.sh 05
⚠️  No AGENT_API_KEY found — running with preset responses (zero-key mode)
    Want the real model? Put AGENT_API_KEY in .env. No code changes needed.

测试 1：查单台设备
DEV-0001 (AAU5613) has 1 active alarm: RF unit VSWR abnormal (major).
```

21 labs run end-to-end with **no key at all** (2 of them are Dify comparison labs that print a guide). Each one has a `_mock_llm.py` whose
preset responses are written to match that lab's teaching point — for the prompt-engineering
lab, the mock deliberately *hallucinates* on the naive prompt and *stays honest* on the
constrained one, so the comparison table actually proves something.

Set `AGENT_API_KEY` and the same code switches to the real model.

---

## Swapping models

Every lab goes through the OpenAI-compatible protocol. Changing providers is two env vars:

| Provider | `AGENT_API_BASE` | `AGENT_MODEL` |
|---|---|---|
| DeepSeek (default) | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Qwen (DashScope) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Local Ollama (free) | `http://localhost:11434/v1` | `qwen2.5:7b` |
| Local vLLM | `http://localhost:8000/v1` | `Qwen/Qwen2.5-7B-Instruct` |

Full details in [docs/模型配置.md](docs/模型配置.md) (Chinese).

---

## Lab index

| # | Lab | Zero-key |
|:--:|---|:--:|
| 01 | StateGraph basics | ✅ |
| 02 | Tool loop | ✅ |
| 03 | Checkpointer & memory | ✅ |
| 04 | Dify agent (low-code comparison) | — |
| 05 | LangChain agent | ✅ |
| 06 | Prompt engineering | ✅ |
| 07 | Tool design conventions | ✅ |
| 08 | Output parsers | ✅ |
| 09 | Agent type comparison | ✅ |
| 10 | RunnableBranch | ✅ |
| 11 | LCEL fundamentals | ✅ |
| 12 | FAISS vector store | — |
| 13 | Cosine similarity | ✅ |
| 14 | RAG agent | — |
| 15 | Dify RAG (comparison) | — |
| 16 | Memory strategies | ✅ |
| 17 | Callbacks & metrics | ✅ |
| 18 | LLM caching | ✅ |
| 19 | RAG evaluation | — |
| 20 | Text-to-SQL | — |
| 21 | Intent routing | — |
| 22 | LangGraph multi-agent | — |
| 23 | Advanced collaboration patterns | — |
| 24 | Human-in-the-loop | ✅ |
| 25 | Observability | ✅ |
| 26 | LLM-as-judge | ✅ |
| 27 | LangServe — graph as HTTP API | ✅ |
| 28 | LangSmith tracing | ✅ |

Labs marked `—` need an API key; RAG labs additionally need an embedding model.

---

## Status

| | |
|---|---|
| Labs | 28 |
| Zero-key runnable | 21 |
| With automated `check.py` | 16 |
| CI | GitHub Actions (no secrets required) |
| Broken relative links | 0 (checked in CI) |

---

## Requirements

macOS or Linux, Python 3.11+. `setup.sh` uses [uv](https://github.com/astral-sh/uv) if
available, otherwise falls back to `python3 -m venv`.

---

## License

MIT — see [LICENSE](LICENSE).
