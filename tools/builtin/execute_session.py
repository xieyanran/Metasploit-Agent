"""
Tool for setting with Metasploit sessions
and execute a command.
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class ExecuteSessionTool(BaseTool):
    name = "execute_session"
    description = "set session id and execute command"

    def __init__(self, client: MetasploitClient, name: str = "execute_session", description: str = "set session id and execute command"):
        self.client = client
        self.name = name
        self.description = description

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="session_id", type="integer", description="Target Metasploit session ID."),
            ToolParameter(name="command", type="string", description="Command to execute in the session."),
        ]

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
            if session_type == "Meterpreter":
                self.client.sessions.meterpreter_write(session_id, command)
                result = self.client.sessions.meterpreter_read(session_id)
                return ToolResult(
                    tool = f"Meterpreter Session Set and Execute a Command",
                    success = True,
                    output = result,
                    message = f"Set session and execute a command successfully."
                )
            elif session_type == "shell":
                self.client.sessions.write(session_id, command + "\n")
                result = self.client.sessions.read(session_id, 0)
                return ToolResult(
                    tool = f"Shell Session Set and Execute a Command",
                    success = True,
                    output = result,
                    message = f"Set session and execute a command successfully."
                )
            # session_type == protocol-specific
            # don't mess up console ID && session ID
            # protocol-specific以后可以扩展
            elif session_type == "protocol-specific":
                console = self.client.console.create()
                console_id = console["id"]

                # 让 Console 进入指定 Session
                self.client.console.write(console_id, f"sessions -i {session_id}\n")
                self.client.console.read(console_id)

                self.client.console.write(console_id, command)
                result = self.client.console.read(console_id)
                return ToolResult(
                    tool = f"Shell Session Set and Execute a Command",
                    success = True,
                    output = result,
                    message = f"Set session and execute a command successfully."
                )

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

