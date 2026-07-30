"""
Tool for killing Meterpreter Sessions
"""
from agent.tools.base import BaseTool
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class KillMeterpreterSessionTool(BaseTool):
    """
    Killing the Metasploit Meterpreter sessions.
    """
    name = "kill_meterpreter_session"
    description = "Kill Metasploit Meterpreter session"

    def __init__(self, client: MetasploitClient):
            self.client = client

    def execute(self, 
                state: AgentState,
                session_id: int,
                ) -> ToolResult:

        session = state.execution.current_session
        session_type = session.get("type", "")

        if session_type is not "Meterpreter":
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
