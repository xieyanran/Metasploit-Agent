"""
Execute the tool selected by the Reasoner
"""
from __future__ import annotations
from agent.state import AgentState, ToolResult, Decision
from agent.tool_registry import ToolRegistry

class ActionExecutor:
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry

    def execute(
        self,
        decision: Decision,
        state: AgentState,
    ) -> ToolResult:
        # The decision have already finished
        if decision.finish:
            return ToolResult(
                tool = "None",
                success = True,
                output = None,
                message = "Reasoning loop finished.",
            )
        # find tool
        tool = self.tool_registry.get(decision.tool)

        if tool is None:
            return ToolResult(
                tool = decision.tool,
                success = False,
                output = None,
                message=f"Unknown tool: {decision.tool}",
            )

        # execute
        return tool.execute(
            state = state,
            **decision.parameters,
        )