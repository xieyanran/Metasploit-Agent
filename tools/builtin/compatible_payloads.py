"""
Tool for discovering payloads compatible with a specific exploit module.
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult


class CompatiblePayloadsTool(BaseTool):
    """
    List payloads compatible with an exploit module, optionally narrowed
    down to one of the module's targets.
    """
    name = "compatible_payloads"
    description = "List payloads compatible with an exploit module (optionally for a specific target index)."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="module_name", type="string", description="Exploit module name (e.g. 'unix/ftp/vsftpd_234_backdoor')."),
            ToolParameter(name="target", type="integer", description="Target index to narrow compatibility to.", required=False, default=None),
        ]

    def execute(self, state: AgentState, module_name: str, target: int = None) -> ToolResult:
        if target is not None:
            result = self.client.modules.target_compatible_payloads(module_name, target)
        else:
            result = self.client.modules.compatible_payloads(module_name)

        return ToolResult(
            tool="compatible_payloads",
            success=True,
            output=result,
            message=f"Compatible payloads for '{module_name}' listed successfully.",
        )
