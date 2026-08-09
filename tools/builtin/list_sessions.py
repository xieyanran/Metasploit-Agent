"""
Tool for listing Sessions
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class ListSessionTool(BaseTool):
    """
    List all the Metasploit sessions.
    """
    name = "list_session"
    description = "List Metasploit session"

    def __init__(self, client: MetasploitClient, name: str = "list_session", description: str = "List Metasploit session"):
        self.client = client
        self.name = name
        self.description = description

    def get_parameters(self) -> List[ToolParameter]:
        return []

    def execute(self, state: AgentState) -> ToolResult:
        state.target.sessions = self.client.sessions.list()
        return ToolResult(
            tool = f"Metaspolit Session List",
            success = True,
            output = state.target.sessions,
            message = f"Session listed successfully."
        )