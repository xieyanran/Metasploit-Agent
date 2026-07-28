"""
Tool for setting module options.
!!! 维护当前 Module 的 options，而不是直接执行 module
"""

from agent.tools.base import BaseTool
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult
class SetOptionTool(BaseTool):
    """
    Configure options for the selected Metasploit module.
    """
    name = "set_option"
    description = "Set one option for the current Metasploit module."

    def __init__(self, client: MetasploitClient):
        self.client = client

    def execute(
            self, 
            state: AgentState,
            options: dict,
            ) -> ToolResult:

        if state.module.module_name is None:
            return ToolResult(
                tool = "use_module",
                success = False,
                output = None,
                message="No module selected."
            )

        # validate 
        available_options = self.client.modules.options(
            state.module.module_type,
            state.module.module_name,
        )

        invalid = [
            name for name in available_options
            if name not in available_options
        ]

        if invalid:
            return ToolResult(
                tool = "set_option",
                success = False,
                message = f"Unknown option(s): {', '.join(invalid)}",
                output = invalid,
            )

        state.module.options = options

        return ToolResult(
            tool = "set_option",
            success = True,
            message = "Module options setting or updating.",
            output = state.module.options
        )

    