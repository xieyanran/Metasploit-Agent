"""
Tool for setting module options.
!!! 维护当前 Module 的 options，而不是直接执行 module
"""

from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult
class SetOptionTool(BaseTool):
    """
    Configure options for the selected Metasploit module.
    """
    name = "set_option"
    description = "Set one option for the current Metasploit module."

    def __init__(self, client: MetasploitClient, name: str = "set_option", description: str = "Set one option for the current Metasploit module."):
        self.client = client
        self.name = name
        self.description = description

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="options", type="object", description="Options to set on the currently selected module, as a dict of option name to value."),
        ]

    def execute(
            self, 
            state: AgentState,
            options: dict, # LLM Reasoning
            ) -> ToolResult:

        if state.module.module_name is None:
            return ToolResult(
                tool = "use_module",
                success = False,
                output = None,
                message = "No module selected."
            )

        # validate
        available_options = self.client.modules.options(
            state.module.module_type,
            state.module.module_name,
        )

        # 模块自身的 module.options() 只包含 RHOSTS/RPORT 这类 exploit 自己的选项，
        # 不包含 payload 专属选项（如 LHOST/LPORT）。一旦本次设置了 PAYLOAD（或之前
        # 已经选定过），需要把该 payload 的 options 一并取出来合并校验，否则
        # LHOST/LPORT 会被误判为 "未知选项"。
        payload_name = options.get("PAYLOAD", state.module.payload)
        if payload_name:
            payload_options = self.client.modules.options("payload", payload_name)
            available_options = {**available_options, **payload_options}

        invalid = [
            name for name in options
            if name != "PAYLOAD" and name not in available_options
        ]

        if invalid:
            return ToolResult(
                tool = "set_option",
                success = False,
                message = f"Unknown option(s): {', '.join(invalid)}",
                output = invalid,
            )

        if "PAYLOAD" in options:
            state.module.payload = options["PAYLOAD"]

        state.module.options = options

        return ToolResult(
            tool = "set_option",
            success = True,
            message = "Module options setting or updating.",
            output = state.module.options
        )

    