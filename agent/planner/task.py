# Task 是 Planner 与 Executor 之间的契约

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Task:
    """
    Represents one executable task.
    """
    id: int
    goal: str
    name: str
    tool: str
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    dependencies: list[int] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    description: str
    error: str | None = None