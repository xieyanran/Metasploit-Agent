"""
Tool for setting with Metasploit sessions.
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

    def execute(self, state: AgentState, session):