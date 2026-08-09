"""
Tool for getting information about a specific Metasploit modules
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class InfoModuleTool(BaseTool):
    """
    Get information about a Metasploit module.
    """
    name = "info_module"
    description = "List information about Metasploit module."

    def __init__(self, client: MetasploitClient, name: str = "info_module", description: str = "List information about Metasploit module."):
        self.client = client
        self.name = name
        self.description = description

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="module_type", type="string", description="Metasploit module type (e.g. exploit, auxiliary, post)."),
            ToolParameter(name="module_name", type="string", description="Metasploit module name."),
        ]

    def execute(self,
                state: AgentState, 
                module_type: str, 
                module_name: str
                ) -> ToolResult:
        result = self.client.modules.info(
            module_type = module_type,
            module_name = module_name
        )
        # print("\n!!!!!!!!!!!!!!!")
        # print(result)

        return ToolResult(
            tool = f"Metaspolit Module '{module_name}'",
            success = True,
            output = result,
            message = f"Module '{module_name}' information list successfully."
        )
    