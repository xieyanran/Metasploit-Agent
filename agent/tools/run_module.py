"""
Tool for running Metasploit modules
"""
from agent.tools.base import BaseTool
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
            message=f"Module '{module_name}' executed successfully."
            )