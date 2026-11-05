"""
Step 5: Skill 系统 — 解析 SKILL.md 文件，让用户教 Agent 新能力

SKILL.md 格式：
```markdown
# Skill Name
## 触发条件
用户提到"XX"或"YY"
## 执行步骤
1. 读取输入文件
2. 调用 tool_xxx
3. 生成报告
## 约束
- 不要修改原文件
- 输出用中文
```
"""

from __future__ import annotations
import os
import re
from typing import Optional


class Skill:
    def __init__(self, name: str, triggers: list[str], steps: list[str], constraints: list[str], source_file: str):
        self.name = name
        self.triggers = triggers
        self.steps = steps
        self.constraints = constraints
        self.source_file = source_file

    def to_prompt(self) -> str:
        lines = [f"## Skill: {self.name}"]
        lines.append(f"触发条件: {', '.join(self.triggers)}")
        lines.append("执行步骤:")
        for s in self.steps:
            lines.append(f"  {s}")
        if self.constraints:
            lines.append(f"约束: {', '.join(self.constraints)}")
        return "\n".join(lines)


def _parse_skill_md(filepath: str) -> Optional[Skill]:
    """解析单个 SKILL.md 文件"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取标题
    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    name = title_match.group(1).strip() if title_match else os.path.basename(os.path.dirname(filepath))

    # 提取触发条件（兼容"触发条件："和"触发条件"两种格式）
    triggers = []
    trigger_section = re.search(r"触发条件[：:]?\s*\n(.+?)(?:\n##|\n#|\Z)", content, re.DOTALL)
    if trigger_section:
        triggers = [t.strip("- ").strip() for t in trigger_section.group(1).strip().split("\n") if t.strip()]

    # 提取执行步骤
    steps = []
    steps_section = re.search(r"执行步骤[：:]?\s*\n(.+?)(?:\n##|\n#|\Z)", content, re.DOTALL)
    if steps_section:
        steps = [s.strip("- ").strip() for s in steps_section.group(1).strip().split("\n") if s.strip()]

    # 提取约束
    constraints = []
    constraint_section = re.search(r"约束[：:]?\s*\n(.+?)(?:\n##|\n#|\Z)", content, re.DOTALL)
    if constraint_section:
        constraints = [c.strip("- ").strip() for c in constraint_section.group(1).strip().split("\n") if c.strip()]

    if not steps:
        return None

    return Skill(name=name, triggers=triggers, steps=steps, constraints=constraints, source_file=filepath)


def load_skills(skills_dir: str = "./skills") -> list[Skill]:
    """加载 skills/ 目录下所有 SKILL.md"""
    skills = []
    if not os.path.exists(skills_dir):
        return skills

    for entry in os.listdir(skills_dir):
        entry_path = os.path.join(skills_dir, entry)
        if os.path.isdir(entry_path):
            md_path = os.path.join(entry_path, "SKILL.md")
            if os.path.exists(md_path):
                skill = _parse_skill_md(md_path)
                if skill:
                    skills.append(skill)
        elif entry.endswith(".md"):
            skill = _parse_skill_md(entry_path)
            if skill:
                skills.append(skill)

    return skills


def match_skill(user_query: str, skills: list[Skill]) -> Optional[Skill]:
    """根据用户输入匹配最相关的 Skill"""
    query_lower = user_query.lower()
    best = None
    best_score = 0

    for skill in skills:
        score = 0
        for trigger in skill.triggers:
            trigger_lower = trigger.lower()
            if trigger_lower in query_lower:
                score += 10
            # 部分匹配也加分
            for word in trigger_lower.split():
                if len(word) > 1 and word in query_lower:
                    score += 3
        if score > best_score:
            best_score = score
            best = skill

    return best if best_score > 5 else None
