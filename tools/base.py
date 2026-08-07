"""
Base interface for all tools in the AI pentesting agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from agent.state import AgentState
from agent.models import ToolResult

class BaseTool(ABC):
    """
    Abstract base class for all executable tools.

    Every tool should implement:
        - name
        - description
        - execute()
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def execute(self, state: AgentState, **kwargs) -> ToolResult:
        """
        Execute the tool.

        Args:
            state: Current agent runtime state.
            **kwargs: Tool-specific parameters.

        Returns:
            ToolResult describing the execution outcome.
        """
        raise NotImplementedError