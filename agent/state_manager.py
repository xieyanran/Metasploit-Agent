# 统一维护状态变更
import datetime

from agent.state import AgentState, ToolCall
from agent.models import Task, ToolResult, Host, Credential, Session, Loot

class StateManager:
    def __init__(self, state: AgentState):
        self.state = state

    # ------------ Task ------------
    def start_task(self, task: Task) -> None:
        self.state.execution.current_task = task
        self.state.execution.running = True
        self.state.execution.error = None

    def finish_task(self, result: ToolResult) -> None:
        self.state.execution.running = False
        self.state.execution.last_result = result
        self.state.execution.step += 1

    def fail_task(self, error: str) -> None:
        self.state.execution.running = False
        self.state.execution.error = error

    # ---------- World Model ----------
    def add_host(self, host: Host) -> None:
        self.state.target.hosts.append(host)

    def add_credential(self, credential: Credential) -> None:
        self.state.target.credentials.append(credential)

    def add_sessions(self, session: Session) -> None:
        self.state.target.sessions.append(session)

    def add_loot(self, loot: Loot) -> None:
        self.state.target.loot.append(loot)

    # ----------—- Planning -----------
    def set_plan(self, tasks: list[Task]) -> None:
        self.state.planning.plan = tasks
        self.state.planning.current_index = 0

    def next_task(self) -> None:
        self.state.planning.current_index += 1

    # ------------- History -------------
    def record_result(self, tool:str, arguments:dict, result: ToolResult) -> None:
        self.state.history.calls.append(
        ToolCall(
            tool=tool,
            arguments=arguments,
            result=result,
            timestamp=datetime.datetime.now(),
        )
    )
        


