"""
Tool for using Metasploit modules
"""
from agent.tools.base import BaseTool
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class UseModuleTool(BaseTool):
    name = "use_module"
    description = "Use Metasploit module."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def execute(self, state: AgentState, keyword: str) -> ToolResult:
        modules = self.client.modules
        