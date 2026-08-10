"""
Central registration point for all built-in Metasploit tools.
"""
from metasploit.client import MetasploitClient
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


def register_builtin_tools(registry: ToolRegistry, client: MetasploitClient) -> None:
    """
    Instantiate and register every built-in tool against the given client.
    """
    registry.register_tool(NmapScanTool(client))
    registry.register_tool(ListSessionTool(client))
    registry.register_tool(ExecuteSessionTool(client))
    registry.register_tool(KillMeterpreterSessionTool(client))
    registry.register_tool(SearchModuleTool(client))
    registry.register_tool(InfoModuleTool(client))
    registry.register_tool(ShowOptionTool(client))
    registry.register_tool(SetOptionTool(client))
    registry.register_tool(RunModuleTool(client))
    registry.register_tool(CompatiblePayloadsTool(client))
    registry.register_tool(ShellUpgradeTool(client))
    registry.register_tool(SessionCompatibleModulesTool(client))
    registry.register_tool(ListJobsTool(client))
    registry.register_tool(JobInfoTool(client))
    registry.register_tool(StopJobTool(client))
    registry.register_tool(StopSessionTool(client))
