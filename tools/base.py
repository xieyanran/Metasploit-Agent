"""
Base interface for all tools in the AI pentesting agent.
Tool基类是整个工具系统的核心抽象，它定义了所有工具必须遵循的接口规范
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from agent.state import AgentState
from agent.models import ToolResult
from typing import Dict, Any, List, Optional, Callable, get_type_hints

def tool_action(name: str = None, description: str = None):
    """装饰器：标记一个方法为可展开的工具 action

    用法:
        @tool_action("memory_add", "添加新记忆")
        def _add_memory(self, content: str, importance: float = 0.5) -> str:
            '''添加记忆

            Args:
                content: 记忆内容
                importance: 重要性分数
            '''
            ...

    Args:
        name: 工具名称（如果不提供，从方法名自动生成）
        description: 工具描述（如果不提供，从 docstring 提取）
    """
    def decorator(func: Callable):
        func._is_tool_action = True
        func._tool_name = name
        func._tool_description = description
        return func
    return decorator

@dataclass
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