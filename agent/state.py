# Agent运行状态（会不断变化）
# 所有组件共享的数据中心

from dataclasses import dataclass, field
import datetime
from enum import Enum
from agent.models import Target, Task, ToolResult, Session
from agent.state import PlanningState, ExecutionState, ModuleState, HistoryState, AgentStatus
from typing import Any

@dataclass
class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    OBSERVING = "observing"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class AgentState:
    status: AgentStatus = AgentStatus.IDLE
    target: Target | None = None
    planning: PlanningState = field(default_factory=PlanningState)
    execution: ExecutionState = field(default_factory=ExecutionState)
    module: ModuleState = field(default_factory=ModuleState)
    history: HistoryState = field(default_factory=HistoryState)
@dataclass
class WorldState:
    """
    The agent's current understanding of the target environment.
    """
    target: Target

# execute task currently
@dataclass
class ExecutionState:
    current_task: Task | None = None
    current_session: Session | None = None
    running: bool = False
    step: int = 0
    last_result: ToolResult | None = None 
    error: str | None = None

# Goal -> Plan -> Task1 -> Task2 -> Task3
@dataclass
class PlanningState:
    goal: str = ""
    plan: list[Task] = field(default_factory=list)
    current_index: int = 0

@dataclass
class ModuleState:
    module_name: str | None = None
    module_type: str | None = None
    payload: str | None = None
    options: dict[str, object] = field(default_factory=dict)
    configured: bool = False

class ToolCall:
    tool: str
    arguments: dict
    result: ToolResult
    timestamp: datetime

@dataclass
class HistoryState:
    calls: list[ToolResult] = field(default_factory=list)

"""
Observation passed to the Reasoner.
- 为什么不直接传 AgentState？
"""
@dataclass
class Observation:
    """
    Snapshot of the current environment.
    This is the only information the Reasoner needs to make decisions.
    """
    target: Target | None = None
    current_task: Task | None = None
    # 需要加入一个model class吗
    current_module: str | None = None
    current_session: Session | None = None
    last_result: Any | None = None
    history: list[Any] = field(default_factory=list)

@dataclass
class Decision:
    tool: str
    parameters: dict
    finish: bool
    reasoning: str
