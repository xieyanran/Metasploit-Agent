"""
Tool for running Metasploit modules
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class RunModuleTool(BaseTool):
    """
    Execute a Metasploit module.
    """
    name = "run_module"
    description = "Run Metasploit module."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="module_type", type="string", description="Metasploit module type (e.g. exploit, auxiliary, post)."),
            ToolParameter(name="module_name", type="string", description="Metasploit module name."),
            ToolParameter(name="options", type="object", description="Module options as a dict of option name to value."),
        ]

    def execute(self,
                state: AgentState, 
                module_type: str,
                module_name: str,
                options: dict,
                ) -> ToolResult:
        result = self.client.modules.execute (
            module_type = module_type,
            module_name = module_name,
            options = options,
        )

        return ToolResult(
            tool = f"Metaspolit Module '{module_name}'",
            success = True,
            output = result,
            message = f"Module '{module_name}' executed successfully."
            )