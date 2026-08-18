"""
Central registration point for all built-in Metasploit tools.
"""
from metasploit.client import MetasploitClient
from core.scope import EngagementScope
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


def register_builtin_tools(registry: ToolRegistry, client: MetasploitClient, scope: EngagementScope) -> None:
    """
    Instantiate and register every built-in tool against the given client.

    `scope` is required (not defaulted) so that wiring a scope guard is never
    accidentally skipped — see core/scope.py. Only tools that can make the
    agent act on a raw target (scan or execute a module) are scope-checked;
    session/job-management tools act on already-established IDs and are out
    of scope for this check.
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
    # semantic 记忆当前依赖 Qdrant/Neo4j 且引用了本项目里不存在的
    # core.database_config 模块，初始化会直接抛异常，因此这里只启用 working/episodic
    # （两者都是本地 SQLite 存储，已验证可用）。如果连这两种都初始化失败（比如
    # memory_data 目录不可写），不应该拖垮其余 16 个 Metasploit 工具的注册。
    try:
        registry.register_tool(MemoryTool(memory_types=["working", "episodic"]))
    except Exception as e:
        print(f"⚠️ 警告: 记忆工具 'memory' 初始化失败，跳过注册: {e}")
