"""
Step 8: 定时任务调度器 — 基于 APScheduler

支持两种调度方式:
1. Cron 表达式 — 精确到分钟级别的周期性任务
2. Interval — 固定间隔执行

每个任务在被触发时执行一次 Agent Run，结果保存到文件。
"""

from __future__ import annotations
import os
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

log = logging.getLogger("scheduler")


class ScheduledTask:
    """单个定时任务定义"""

    def __init__(
        self,
        name: str,
        schedule: str,
        prompt: str,
        enabled: bool = True,
        task_type: str = "cron",
        workspace: str = "./workspace",
    ):
        self.name = name
        self.schedule = schedule  # cron expr 或 interval 秒数
        self.prompt = prompt
        self.enabled = enabled
        self.task_type = task_type  # "cron" | "interval"
        self.workspace = workspace
        self.last_run: Optional[datetime] = None
        self.last_result: str = ""
        self.run_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "schedule": self.schedule,
            "prompt": self.prompt,
            "enabled": self.enabled,
            "task_type": self.task_type,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_result": self.last_result[:200],
            "run_count": self.run_count,
        }


def load_tasks_from_yaml(filepath: str) -> list[ScheduledTask]:
    """从 YAML 文件加载任务定义"""
    tasks = []

    try:
        import yaml
    except ImportError:
        log.warning("⚠️  PyYAML 未安装，使用 JSON 格式加载 tasks.json")
        return _load_tasks_from_json(filepath.replace(".yaml", ".json"))

    if not os.path.exists(filepath):
        log.warning(f"⚠️  任务配置文件不存在: {filepath}，使用默认任务")
        return _default_tasks()

    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []

    # 兼容两种格式：直接列表 或 {tasks: [...]}
    if isinstance(data, dict):
        data = data.get("tasks", [])
    if not isinstance(data, list):
        data = []

    for item in data:
        tasks.append(ScheduledTask(
            name=item.get("name", "Unnamed"),
            schedule=item.get("schedule", ""),
            prompt=item.get("prompt", ""),
            enabled=item.get("enabled", True),
            task_type=item.get("type", "cron"),
            workspace=item.get("workspace", "./workspace"),
        ))

    return tasks


def _load_tasks_from_json(filepath: str) -> list[ScheduledTask]:
    """Fallback: JSON 格式加载"""
    if not os.path.exists(filepath):
        return _default_tasks()
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    tasks = []
    for item in data:
        tasks.append(ScheduledTask(
            name=item.get("name", "Unnamed"),
            schedule=item.get("schedule", ""),
            prompt=item.get("prompt", ""),
            enabled=item.get("enabled", True),
            task_type=item.get("type", "cron"),
            workspace=item.get("workspace", "./workspace"),
        ))
    return tasks


def _default_tasks() -> list[ScheduledTask]:
    """内置默认任务（示范用）"""
    return [
        ScheduledTask(
            name="每小时健康检查",
            schedule="0 * * * *",
            prompt="检查 workspace 目录是否有新生成的文件，如有列出文件名",
            task_type="cron",
        ),
        ScheduledTask(
            name="每日数据汇总（模拟）",
            schedule="0 9 * * *",
            prompt="读取 sales.csv，生成昨日销售数据汇总",
            task_type="cron",
        ),
    ]


class TaskScheduler:
    """
    APScheduler 调度器封装

    职责：
    1. 接收 Agent Graph 引用，在任务触发时执行 Agent Run
    2. 管理任务生命周期（启动/暂停/恢复）
    3. 持久化执行日志
    """

    def __init__(self, graph: Any, workspace: str, log_dir: str = "./task_logs"):
        self.graph = graph
        self.workspace = workspace
        self.log_dir = log_dir
        self.tasks: list[ScheduledTask] = []
        self._scheduler = None
        self._running = False

    def load_tasks(self, config_path: str) -> None:
        """加载任务配置"""
        self.tasks = load_tasks_from_yaml(config_path)
        log.info(f"📋 已加载 {len(self.tasks)} 个定时任务")

    def start(self) -> None:
        """启动调度器"""
        if self._running:
            return

        from apscheduler.schedulers.background import BackgroundScheduler

        self._scheduler = BackgroundScheduler(daemon=True)

        for task in self.tasks:
            if not task.enabled:
                continue

            job_id = f"task-{task.name}"

            if task.task_type == "cron":
                # 解析 cron 表达式
                parts = task.schedule.strip().split()
                if len(parts) == 5:
                    self._scheduler.add_job(
                        self._execute_task,
                        trigger="cron",
                        args=[task],
                        id=job_id,
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4],
                        replace_existing=True,
                    )
                else:
                    log.error(f"❌ 无效的 cron 表达式: {task.schedule} (task: {task.name})")
            elif task.task_type == "interval":
                seconds = int(task.schedule)
                self._scheduler.add_job(
                    self._execute_task,
                    trigger="interval",
                    args=[task],
                    id=job_id,
                    seconds=seconds,
                    replace_existing=True,
                )

        self._scheduler.start()
        self._running = True
        log.info(f"⏰ 调度器已启动，{len([t for t in self.tasks if t.enabled])} 个任务就绪")

    def stop(self) -> None:
        """停止调度器"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._running = False
            log.info("⏹️  调度器已停止")

    def get_status(self) -> dict[str, Any]:
        """返回调度器状态"""
        return {
            "running": self._running,
            "task_count": len(self.tasks),
            "tasks": [t.to_dict() for t in self.tasks],
        }

    def _execute_task(self, task: ScheduledTask) -> None:
        """执行单个定时任务 — 运行一次 Agent Loop"""
        from datetime import datetime

        session_id = str(uuid.uuid4())[:8]
        task.run_count += 1
        task.last_run = datetime.now()

        log.info(f"⏰ [{task.name}] 开始执行 (第 {task.run_count} 次)")
        log.info(f"   Prompt: {task.prompt[:100]}...")

        os.makedirs(self.log_dir, exist_ok=True)

        try:
            initial_state = {
                "user_input": task.prompt,
                "workspace_path": self.workspace,
                "session_id": session_id,
                "intent": "",
                "enriched_context": "",
                "matched_skill": None,
                "plan": [],
                "current_step": 0,
                "tool_results": [],
                "validation_passed": False,
                "validation_feedback": "",
                "retry_count": 0,
                "final_output": "",
                "output_files": [],
            }

            config = {"configurable": {"thread_id": f"sched-{session_id}"}}

            # 同步执行 Agent Graph
            result = self.graph.invoke(initial_state, config)

            final_output = result.get("final_output", "")
            task.last_result = final_output[:500]

            # 持久化执行日志
            log_file = os.path.join(
                self.log_dir,
                f"{task.name}-{task.last_run.strftime('%Y%m%d-%H%M%S')}.json",
            )
            log_entry = {
                "task": task.name,
                "run": task.run_count,
                "time": task.last_run.isoformat(),
                "session_id": session_id,
                "prompt": task.prompt,
                "result": final_output[:2000],
                "output_files": result.get("output_files", []),
            }
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2)

            log.info(f"✅ [{task.name}] 完成 ({len(final_output)} 字符) → {log_file}")

        except Exception as e:
            task.last_result = f"Error: {e}"
            log.error(f"❌ [{task.name}] 执行失败: {e}", exc_info=True)

            # 错误日志
            error_file = os.path.join(
                self.log_dir,
                f"{task.name}-ERROR-{task.last_run.strftime('%Y%m%d-%H%M%S')}.txt",
            )
            with open(error_file, "w", encoding="utf-8") as f:
                f.write(f"Task: {task.name}\nTime: {task.last_run.isoformat()}\nError: {e}\n")
