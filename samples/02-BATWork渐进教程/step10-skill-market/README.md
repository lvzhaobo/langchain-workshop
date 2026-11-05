# Step 10: + Skill 市场生态

> 从"一个示例 Skill"到"可运营的 Skill 市场"。内置 5 个真实领域 Skill，支持 Skill 市场的安装/卸载/热重载完整生态闭环。

## 新增能力

| 能力 | 说明 |
|:---|:---|
| **5 个真实 Skill** | 竞品分析、数据可视化、邮件撰写、月报、周报 |
| **Skill 市场 API** | 浏览可安装 Skill，一键安装/卸载 |
| **热重载** | 安装/卸载后无需重启服务，Skill 即时生效 |
| **生态闭环** | 用户可基于 Skill 模板创建自定义 Skill |

## 启动方式

```bash
# 启动后自动加载 5 个 Skill
python server.py --port 6001 --model qwen2.5:0.5b

# 浏览器打开 Skill 管理
open http://localhost:6001

# 查看已安装 Skill
curl http://localhost:6001/api/skills

# 浏览 Skill 市场
curl http://localhost:6001/api/skills/marketplace
```

## 内置 Skill 清单

| Skill | 触发关键词 | 说明 |
|:---|:---|:---|
| **月度经营分析报告** | 月度报告、经营分析、月报 | 自动分析销售数据，生成结构化月度经营报告 |
| **竞品分析报告** | 竞品分析、竞争对手、市场对比 | 多维度对比分析，生成 SWOT 和策略建议 |
| **客户邮件撰写** | 写邮件、客户邮件、商务邮件 | 根据商务场景自动生成专业邮件模板 |
| **数据可视化图表** | 数据可视化、图表、趋势图 | CSV 数据转交互式 HTML 图表 |
| **每周工作周报** | 周报、每周总结、工作汇报 | 基于项目文件自动汇总生成周报 |

## 文件结构

```
step10-skill-market/
├── skills/
│   ├── monthly-report/SKILL.md        # 月度经营分析报告
│   ├── competitor-analysis/SKILL.md   # 竞品分析报告
│   ├── email-composer/SKILL.md        # 客户邮件撰写
│   ├── data-viz/SKILL.md              # 数据可视化图表
│   └── weekly-summary/SKILL.md        # 每周工作周报
├── server.py              # 含 /api/skills/marketplace 等端点
├── ... (同 step9 的全部文件)
└── memory_data/           # 记忆数据（自动生成）
```

## Skill API 完整清单

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/api/skills` | GET | 已安装 Skill 列表 |
| `/api/skills/marketplace` | GET | Skill 市场（含安装状态标记） |
| `/api/skills/install/{id}` | POST | 从市场安装 Skill |
| `/api/skills/uninstall/{id}` | POST | 卸载指定 Skill |
| `/api/skills/reload` | POST | 热重载所有 Skill |

## 如何扩展 Skill

在 `server.py` 的 `SKILL_MARKETPLACE` 列表中添加 Skill 定义：

```python
{
    "id": "my-custom-skill",
    "name": "我的自定义 Skill",
    "description": "Skill 功能描述",
    "triggers": ["触发词1", "触发词2"],
    "category": "自定义",
    "premium": False,
}
```

并在 `steps_map` 和 `constraints_map` 中添加对应条目，即可在 Skill 市场中展示和安装。
