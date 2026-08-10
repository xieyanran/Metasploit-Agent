"""
Tool for getting information about a specific Metasploit job.
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult


class JobInfoTool(BaseTool):
    """
    Get information about a specific job, e.g. to check whether a
    background exploit has produced a session yet.
    """
    name = "job_info"
    description = "Get information about a specific Metasploit job."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="job_id", type="integer", description="Job ID to inspect."),
        ]

    def execute(self, state: AgentState, job_id: int) -> ToolResult:
        result = self.client.jobs.info(job_id)
        return ToolResult(
            tool="job_info",
            success=True,
            output=result,
            message=f"Job {job_id} information listed successfully.",
        )
