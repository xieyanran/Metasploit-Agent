# Agent运行状态（会不断变化）
# 所有组件共享的数据中心
# circular import issue
from dataclasses import dataclass, field
from agent.models import Target, Session

# execute task currently
@dataclass
class ExecutionState:
    current_session: Session | None = None

@dataclass
class ModuleState:
    module_name: str | None = None
    module_type: str | None = None
    payload: str | None = None
    options: dict[str, object] = field(default_factory=dict)
    configured: bool = False

@dataclass
class AgentState:
    target: Target | None = None
    execution: ExecutionState = field(default_factory=ExecutionState)
    module: ModuleState = field(default_factory=ModuleState)
    # PTES阶段：recon/Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation，
    ptes_phase: str = "recon"
