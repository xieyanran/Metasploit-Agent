"""
Tool for running Metasploit modules
"""
from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from core.scope import EngagementScope
from agent.state import AgentState
from agent.models import ToolResult

class RunModuleTool(BaseTool):
    """
    Execute a Metasploit module.
    """
    name = "run_module"
    description = "Run Metasploit module."

    def __init__(self, client: MetasploitClient, scope: EngagementScope, name: str = "run_module", description: str = "Run Metasploit module."):
        self.client = client
        self.scope = scope
        self.name = name
        self.description = description

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="module_type", type="string", description="Metasploit module type (e.g. exploit, auxiliary, post)."),
            ToolParameter(name="module_name", type="string", description="Full Metasploit module path as returned by search_module's 'fullname' field (e.g. exploit/multi/http/struts2_content_type_ognl) — must include the exploit/multi/... type prefix, not just the short module name."),
            ToolParameter(name="options", type="object", description="Module options as a dict of option name to value."),
        ]

    def execute(self,
                state: AgentState,
                module_type: str,
                module_name: str,
                options: dict,
                ) -> ToolResult:
        host = options.get("RHOSTS") or options.get("RHOST") or (
            state.target.address if state.target else None
        )
        violation = self.scope.authorize(
            host or "",
            tool_name=self.name,
            require_exploit=(module_type == "exploit"),
        )
        if violation:
            return ToolResult(
                tool=f"Metaspolit Module '{module_name}'",
                success=False,
                output=None,
                message=f"Blocked by scope guard: {violation}",
            )

        result = self.client.modules.execute (
            module_type = module_type,
            module_name = module_name,
            options = options,
        )

        # msfrpcd 的 module.execute 对一个实际不存在/参数不合法的模块，往往不会抛异常，
        # 而是静默返回 {'job_id': None, 'uuid': None}——之前这里无条件返回 success=True，
        # 会把"RPC 调用本身没报错"误判成"利用已经派发"，跟 README 里"成功与否由真实
        # job_id 独立验证，而非自我汇报"这条设计承诺直接矛盾。
        job_id = result.get("job_id") if isinstance(result, dict) else None
        if job_id is None:
            return ToolResult(
                tool = f"Metaspolit Module '{module_name}'",
                success = False,
                output = result,
                message = f"Module '{module_name}' did not return a job_id — dispatch likely failed (invalid module/options?).",
            )

        return ToolResult(
            tool = f"Metaspolit Module '{module_name}'",
            success = True,
            output = result,
            message = f"Module '{module_name}' executed successfully."
            )