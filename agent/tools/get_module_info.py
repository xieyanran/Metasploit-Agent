"""
Tool for getting information about a specific Metasploit modules
"""
from agent.tools.base import BaseTool
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class InfoModuleTool(BaseTool):
    """
    Get information about a Metasploit module.
    """
    name = "info_module"
    description = "List information about Metasploit module."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def execute(self, 
                state: AgentState, 
                module_type: str, 
                module_name: str
                ) -> ToolResult:
        result = self.client.modules.info(
            module_type = module_type,
            module_name = module_name
        )

        return ToolResult(
            tool = f"Metaspolit Module '{module_name}'",
            success = True,
            output = result,
            message = f"Module '{module_name}' information list successfully."
        )
    