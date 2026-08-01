from agent.tools.base import BaseTool
class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name) -> BaseTool:
        return self._tools.get(name)