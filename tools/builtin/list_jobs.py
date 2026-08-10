"""
Tool for listing running Metasploit jobs (e.g. pending exploit listeners).
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult


class ListJobsTool(BaseTool):
    """
    List all running jobs in the Metasploit framework.
    """
    name = "list_jobs"
    description = "List running Metasploit jobs (e.g. exploit listeners waiting for a callback)."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def get_parameters(self) -> List[ToolParameter]:
        return []

    def execute(self, state: AgentState) -> ToolResult:
        result = self.client.jobs.list()
        return ToolResult(
            tool="list_jobs",
            success=True,
            output=result,
            message="Jobs listed successfully.",
        )
