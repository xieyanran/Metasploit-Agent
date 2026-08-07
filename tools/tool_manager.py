from __future__ import annotations
from agent.models import ToolResult
from tools.base import BaseTool

class ToolManager:
    def __init__(self) -> None:
        # Registry O(1)
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a registered tool."""
        self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool:
        """Get a tool by name."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def execute(self, name: str, state, **kwargs) -> ToolResult:
        """
        Execute a registered tool.
        """
        tool = self.get(name)
        return tool.execute(state, **kwargs)