"""
Tool for stopping a running Metasploit job (e.g. a stale exploit listener).
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult


class StopJobTool(BaseTool):
    """
    Stop a specific job in the Metasploit framework.
    """
    name = "stop_job"
    description = "Stop a running Metasploit job."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="job_id", type="integer", description="Job ID to stop."),
        ]

    def execute(self, state: AgentState, job_id: int) -> ToolResult:
        result = self.client.jobs.stop(job_id)
        return ToolResult(
            tool="stop_job",
            success=True,
            output=result,
            message=f"Job {job_id} stopped successfully.",
        )
