"""
Tool for setting module options.
!!! 维护当前 Module 的 options，而不是直接执行 module
"""

from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from core.scope import EngagementScope
from agent.state import AgentState
from agent.models import ToolResult
class SetOptionTool(BaseTool):
    """
    Configure options for the selected Metasploit module.
    """
    name = "set_option"
    description = "Set one option for the current Metasploit module."

    def __init__(self, client: MetasploitClient, scope: EngagementScope, name: str = "set_option", description: str = "Set one option for the current Metasploit module."):
        self.client = client
        self.scope = scope
        self.name = name
        self.description = description

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="module_type", type="string", description="Metasploit module type (e.g. exploit, auxiliary, post)."),
            ToolParameter(name="module_name", type="string", description="Full Metasploit module path as returned by search_module's 'fullname' field (e.g. exploit/multi/http/struts2_content_type_ognl) — must include the exploit/multi/... type prefix, not just the short module name."),
            ToolParameter(name="options", type="object", description="Options to set on the module, as a dict of option name to value."),
        ]

    def execute(
            self,
            state: AgentState,
            module_type: str,
            module_name: str,
            options: dict, # LLM Reasoning
            ) -> ToolResult:

        # validate
        available_options = self.client.modules.options(
            module_type,
            module_name,
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

        # Fast-fail here so an out-of-scope target is caught before the agent
        # spends further planning steps configuring a module it can never run.
        # This is a nicety, not the security boundary itself — run_module's
        # own scope check is what actually gates execution.
        host = options.get("RHOSTS") or options.get("RHOST")
        if host:
            violation = self.scope.authorize(host, tool_name=self.name)
            if violation:
                return ToolResult(
                    tool = "set_option",
                    success = False,
                    message = f"Blocked by scope guard: {violation}",
                    output = None,
                )

        if "PAYLOAD" in options:
            state.module.payload = options["PAYLOAD"]

        # 累加而非覆盖：调用方按"每次设置一个/几个选项"的方式多次调用本工具，
        # 之前已设置好的选项（如 RHOSTS）不应被本次调用清空。
        state.module.module_type = module_type
        state.module.module_name = module_name
        state.module.options = {**state.module.options, **options}

        return ToolResult(
            tool = "set_option",
            success = True,
            message = "Module options setting or updating.",
            output = state.module.options
        )

    