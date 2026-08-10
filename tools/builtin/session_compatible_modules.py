"""
Tool for discovering modules compatible with an existing session.
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult


class SessionCompatibleModulesTool(BaseTool):
    """
    List Metasploit modules (typically post-exploitation) compatible with
    an existing session's platform/type.
    """
    name = "session_compatible_modules"
    description = "List modules compatible with an existing session."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="session_id", type="integer", description="Session ID to find compatible modules for."),
        ]

    def execute(self, state: AgentState, session_id: int) -> ToolResult:
        result = self.client.sessions.compatible_modules(session_id)
        return ToolResult(
            tool="session_compatible_modules",
            success=True,
            output=result,
            message=f"Compatible modules for session {session_id} listed successfully.",
        )
