"""
Central registration point for all built-in Metasploit tools.
"""
from typing import Optional

from metasploit.client import MetasploitClient
from core.scope import EngagementScope
from core.llm import PentestAgentLLM
from tools.registry import ToolRegistry

from tools.builtin.nmap_scan import NmapScanTool
from tools.builtin.list_sessions import ListSessionTool
from tools.builtin.execute_session import ExecuteSessionTool
from tools.builtin.kill_meterpreter_session import KillMeterpreterSessionTool
from tools.builtin.search_module import SearchModuleTool
from tools.builtin.get_module_info import InfoModuleTool
from tools.builtin.show_option import ShowOptionTool
from tools.builtin.set_option import SetOptionTool
from tools.builtin.run_module import RunModuleTool
from tools.builtin.compatible_payloads import CompatiblePayloadsTool
from tools.builtin.shell_upgrade import ShellUpgradeTool
from tools.builtin.session_compatible_modules import SessionCompatibleModulesTool
from tools.builtin.list_jobs import ListJobsTool
from tools.builtin.job_info import JobInfoTool
from tools.builtin.stop_job import StopJobTool
from tools.builtin.stop_session import StopSessionTool
from tools.builtin.memory_tool import MemoryTool


def register_builtin_tools(
    registry: ToolRegistry,
    client: MetasploitClient,
    scope: EngagementScope,
    llm: Optional[PentestAgentLLM] = None,
) -> None:
    """
    Instantiate and register every built-in tool against the given client.

    `scope` is required (not defaulted) so that wiring a scope guard is never
    accidentally skipped — see core/scope.py. Only tools that can make the
    agent act on a raw target (scan or execute a module) are scope-checked;
    session/job-management tools act on already-established IDs and are out
    of scope for this check.

    `llm` is optional and currently only used by MemoryTool, to let manually
    written semantic memories go through SemanticMemoryMaintainer's dedup/
    contradiction check (see MemoryTool._add_memory). Existing call sites that
    don't pass it keep working exactly as before — this is additive, not a
    new hard requirement.
    """
    registry.register_tool(NmapScanTool(client, scope))
    registry.register_tool(ListSessionTool(client))
    registry.register_tool(ExecuteSessionTool(client))
    registry.register_tool(KillMeterpreterSessionTool(client))
    registry.register_tool(SearchModuleTool(client))
    registry.register_tool(InfoModuleTool(client))
    registry.register_tool(ShowOptionTool(client))
    registry.register_tool(SetOptionTool(client, scope))
    registry.register_tool(RunModuleTool(client, scope))
    registry.register_tool(CompatiblePayloadsTool(client))
    registry.register_tool(ShellUpgradeTool(client))
    registry.register_tool(SessionCompatibleModulesTool(client))
    registry.register_tool(ListJobsTool(client))
    registry.register_tool(JobInfoTool(client))
    registry.register_tool(StopJobTool(client))
    registry.register_tool(StopSessionTool(client))

    # "memory" 工具此前从未在这里注册，导致 core.agent.Agent._get_memory_extractor()
    # 里的 tool_registry.get_tool("memory") 一直静默返回 None，记忆子系统全程空转。
    # semantic 记忆依赖本地 Qdrant/Neo4j（见 docker-compose.memory.yml + 根目录
    # README.md「Preparations」），未启动时下面的 try/except 会跳过整个 memory 工具
    # 的注册而不拖垮其余 16 个 Metasploit 工具——working/episodic 是纯本地 SQLite，
    # 不受影响，理论上可以单独降级注册，但目前没有实际需求需要这么做。
    try:
        registry.register_tool(MemoryTool(memory_types=["working", "episodic", "semantic"], llm=llm))
    except Exception as e:
        print(f"⚠️ 警告: 记忆工具 'memory' 初始化失败，跳过注册: {e}")
