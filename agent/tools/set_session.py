"""
Tool for setting with Metasploit sessions
and execute a command.
"""
from agent.tools.base import BaseTool
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class SetSessionTool(BaseTool):
    name = "set_session"
    description = "Set session id"

    def __init__(self, client: MetasploitClient):
        self.client = client

    def execute(self, 
                state: AgentState, 
                session_id: int,
                command: str,
                ) -> ToolResult:

        # check the session_id exits or not
        sessions = state.target.sessions

        if session_id not in sessions:
            return ToolResult(
                tool = "set_session",
                success = False,
                output = None,
                message = "The session_id is not exit."
            )

        session = sessions[session_id]
        session_type = session.get("type", "")
        state.execution.current_session = session

        try:
            if session_type == Meterpreter:
                self.client.sessions.meterpreter_write(session_id, command)
                result = self.client.sessions.meterpreter_read(session_id)
                return ToolResult(
                    tool = f"Meterpreter Session Set and Execute a Command",
                    success = True,
                    output = result,
                    message = f"Set session and execute a command successfully."
                )
            elif session_type == shell:
                self.client.sessions.write(session_id, command + "\n")
                result = self.client.sessions.read(session_id, 0)
                return ToolResult(
                    tool = f"Shell Session Set and Execute a Command",
                    success = True,
                    output = result,
                    message = f"Set session and execute a command successfully."
                )
            # session_type == protocol-specific

            else:
                return ToolResult(
                    success = False,
                    output = f"Unsupported session type: {session_type}",
                    message = f"Set session unsuccessfully."
                )
        
        except Exception as e:
            return ToolResult(
                tool = f"Meterpreter Session Set and Execute a Command",
                success = False,
                output = dict(e),
            )

