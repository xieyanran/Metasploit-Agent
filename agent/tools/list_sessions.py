"""
Tool for listing Sessions
"""
from agent.tools.base import BaseTool
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class ListSessionTool(BaseTool):
    """
    List all the Metasploit sessions.
    """
    name = "list_session"
    description = "List Metasploit session"

    def __init__(self, client: MetasploitClient):
        self.client = client

    def execute(self, state: AgentState) -> ToolResult:
        state.target.sessions = self.client.sessions.list()
        return ToolResult(
            tool = f"Metaspolit Session List",
            success = True,
            output = state.target.sessions,
            message = f"Session listed successfully."
        )