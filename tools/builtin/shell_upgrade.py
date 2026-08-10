"""
Tool for upgrading a shell session to a Meterpreter session.
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult


class ShellUpgradeTool(BaseTool):
    """
    Upgrade an existing shell session to a Meterpreter session.
    """
    name = "shell_upgrade"
    description = "Upgrade a shell session to a Meterpreter session."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="session_id", type="integer", description="Shell session ID to upgrade."),
            ToolParameter(name="lhost", type="string", description="Local host to receive the upgraded Meterpreter callback."),
            ToolParameter(name="lport", type="integer", description="Local port to receive the upgraded Meterpreter callback."),
        ]

    def execute(self, state: AgentState, session_id: int, lhost: str, lport: int) -> ToolResult:
        result = self.client.sessions.shell_upgrade(session_id, lhost, lport)
        return ToolResult(
            tool="shell_upgrade",
            success=True,
            output=result,
            message=f"Session {session_id} upgrade to Meterpreter requested.",
        )
