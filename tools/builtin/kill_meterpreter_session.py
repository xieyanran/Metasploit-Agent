"""
Tool for killing Meterpreter Sessions
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class KillMeterpreterSessionTool(BaseTool):
    """
    Killing the Metasploit Meterpreter sessions.
    """
    name = "kill_meterpreter_session"
    description = "Kill Metasploit Meterpreter session"

    def __init__(self, client: MetasploitClient, name: str = "kill_meterpreter_session", description: str = "Kill Metasploit Meterpreter session"):
        self.client = client
        self.name = name
        self.description = description

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="session_id", type="integer", description="Meterpreter session ID to kill."),
        ]

    def execute(self,
                state: AgentState,
                session_id: int,
                ) -> ToolResult:

        sessions = self.client.sessions.list()
        session = sessions.get(session_id, sessions.get(str(session_id)))

        if session is None:
             return ToolResult(
                  tool = f"Meterpreter Session Kill",
                  success = False,
                  output = f"Session {session_id} not found.",
            )

        session_type = session.get("type", "")

        if session_type != "Meterpreter":
             return ToolResult(
                  tool = f"Meterpreter Session Kill",
                  success = False,
                  output = f"Unsupported session type: {session_type}",
             )

        result = self.client.sessions.meterpreter_session_kill(session_id)

        return ToolResult(
             tool = f"Meterpreter Session Kill",
             success = True,
             output = result,
             message = f"Kill the meterpreter session successfully"
        )
