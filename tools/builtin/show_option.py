"""
Agent -> show options (得到模块需要的参数) -> LLM/Planner
-> set option -> validate -> run module
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class ShowOptionTool(BaseTool):
    """
    对一个特定module的show options命令
    """
    name = "show_option"
    description = "Show Metasploit module options"

    def __init__(self, client: MetasploitClient, name: str = "show_option", description: str = "Show Metasploit module options"):
        self.client = client
        self.name = name
        self.description = description

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="module_type", type="string", description="Metasploit module type (e.g. exploit, auxiliary, post)."),
            ToolParameter(name="module_name", type="string", description="Full Metasploit module path as returned by search_module's 'fullname' field (e.g. exploit/multi/http/struts2_content_type_ognl) — must include the exploit/multi/... type prefix, not just the short module name."),
        ]

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