"""
Base interface for all tools in the AI pentesting agent.
Tool基类是整个工具系统的核心抽象，它定义了所有工具必须遵循的接口规范
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from agent.state import AgentState
from agent.models import ToolResult
from typing import Any, List

class ToolParameter:
    """
    Represents a parameter required by a tool.
    """
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None

class BaseTool(ABC):
    """
    Abstract base class for all executable tools.

    Every tool should implement:
        - name
        - description
        - execute()
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description


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

    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """
        Get the parameters required by the tool.

        Returns:
            A dictionary describing the tool's parameters.
        """
        pass