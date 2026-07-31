# planner可能生成一个task的DAG
# 用于管理任务依赖
from __future__ import annotations
from agent.planner.task import Task, TaskStatus

class TaskGraph:
    def __init__(self):
        self.tasks: dict[int, Task] = {}

    def add_task(self, task: Task):
        self.tasks[task.id] = task

    def get_ready_tasks(self):
        ready = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            ok = True
            for dep in task.dependencies:
                if self.tasks[dep].status != TaskStatus.COMPLETED:
                    ok = False
                    break
            if ok:
                ready.append(task)
        return ready

    def is_finished(self):
        return all(
            task.status in (TaskStatus.COMPLETED)
            for task in self.tasks.values()
        )

    