"""
Agent -> show options (得到模块需要的参数) -> LLM/Planner
-> set option -> validate -> run module
"""
from agent.tools.base import BaseTool
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class ShowOptionTool(BaseTool):
    """
    对一个特定module的show options命令
    """
    name = "show_option"
    description = "Show Metasploit module options"

    def __init__(self, client: MetasploitClient):
        self.client = client

    def execute(self, 
                state: AgentState,
                module_type: str,
                module_name: str,
                ) -> ToolResult:
        result = self.client.modules.options (
            module_type = module_type,
            module_name = module_name,
        )

        return ToolResult(
            tool = f"Metaspolit Module '{module_name}' show options",
            success = True,
            output = result,
            message = f"Module '{module_name}' show options successfully."
        )