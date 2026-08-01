# collect current state
from __future__ import annotations
from agent.state import AgentState, Observation

class Observer:
    """
    Collect the current environment information from AgentState.
    """

    def observe(self, state: AgentState) -> Observation:
        """
        Build an Observation from the current AgentState.
        """
        return Observation(
            target = state.target,
            current_task = state.execution.current_task,
            current_module = state.module,
            current_session = state.execution.current_session,
            last_result = state.execution.last_result,
            history = state.history,
        )