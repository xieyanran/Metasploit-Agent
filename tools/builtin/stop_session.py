"""
Tool for stopping a session (any type, unlike kill_meterpreter_session
which only handles Meterpreter sessions).
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult


class StopSessionTool(BaseTool):
    """
    Stop any active Metasploit session, regardless of its type.
    """
    name = "stop_session"
    description = "Stop a Metasploit session of any type (shell, Meterpreter, etc.)."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="session_id", type="integer", description="Session ID to stop."),
        ]

    def execute(self, state: AgentState, session_id: int) -> ToolResult:
        result = self.client.sessions.stop(session_id)
        return ToolResult(
            tool="stop_session",
            success=True,
            output=result,
            message=f"Session {session_id} stopped successfully.",
        )
