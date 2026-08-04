"""
Adapts the existing agent/tools/*.py BaseTool implementations to LangChain's
tool interface, without changing their execution logic. Each wrapper closes
over a single shared AgentState so tools that read/write state (set_option,
execute_session, ...) keep working exactly as they do in the custom loop.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from langchain_core.tools import StructuredTool

from agent.models import ToolResult
from agent.state import AgentState
from agent.tools.base import BaseTool
from agent.tools.execute_session import ExecuteSessionTool
from agent.tools.get_module_info import InfoModuleTool
from agent.tools.kill_meterpreter_session import KillMeterpreterSessionTool
from agent.tools.list_sessions import ListSessionTool
from agent.tools.nmap_scan import NmapScanTool
from agent.tools.run_module import RunModuleTool
from agent.tools.search_module import SearchModuleTool
from agent.tools.set_option import SetOptionTool
from agent.tools.show_option import ShowOptionTool


def _json_default(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


def _render(result: ToolResult) -> str:
    payload = {"success": result.success, "message": result.message, "output": result.output}
    return json.dumps(payload, default=_json_default)


def _wrap_nmap_scan(tool: NmapScanTool, state: AgentState) -> StructuredTool:
    def run(target: str, options: str = "-sV") -> str:
        return _render(tool.execute(state, target=target, options=options))

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description)


def _wrap_search_module(tool: SearchModuleTool, state: AgentState) -> StructuredTool:
    def run(query: str) -> str:
        return _render(tool.execute(state, query=query))

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description)


def _wrap_info_module(tool: InfoModuleTool, state: AgentState) -> StructuredTool:
    def run(module_type: str, module_name: str) -> str:
        return _render(tool.execute(state, module_type=module_type, module_name=module_name))

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description)


def _wrap_show_option(tool: ShowOptionTool, state: AgentState) -> StructuredTool:
    def run(module_type: str, module_name: str) -> str:
        return _render(tool.execute(state, module_type=module_type, module_name=module_name))

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description)


def _wrap_set_option(tool: SetOptionTool, state: AgentState) -> StructuredTool:
    def run(options: dict[str, Any]) -> str:
        return _render(tool.execute(state, options=options))

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description)


def _wrap_run_module(tool: RunModuleTool, state: AgentState) -> StructuredTool:
    def run(module_type: str, module_name: str, options: dict[str, Any]) -> str:
        return _render(
            tool.execute(state, module_type=module_type, module_name=module_name, options=options)
        )

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description)


def _wrap_list_sessions(tool: ListSessionTool, state: AgentState) -> StructuredTool:
    def run() -> str:
        return _render(tool.execute(state))

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description)


def _wrap_execute_session(tool: ExecuteSessionTool, state: AgentState) -> StructuredTool:
    def run(session_id: int, command: str) -> str:
        return _render(tool.execute(state, session_id=session_id, command=command))

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description)


def _wrap_kill_meterpreter_session(tool: KillMeterpreterSessionTool, state: AgentState) -> StructuredTool:
    def run(session_id: int) -> str:
        return _render(tool.execute(state, session_id=session_id))

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description)


_ADAPTERS: dict[type[BaseTool], Any] = {
    NmapScanTool: _wrap_nmap_scan,
    SearchModuleTool: _wrap_search_module,
    InfoModuleTool: _wrap_info_module,
    ShowOptionTool: _wrap_show_option,
    SetOptionTool: _wrap_set_option,
    RunModuleTool: _wrap_run_module,
    ListSessionTool: _wrap_list_sessions,
    ExecuteSessionTool: _wrap_execute_session,
    KillMeterpreterSessionTool: _wrap_kill_meterpreter_session,
}


def build_langchain_tools(tools: list[BaseTool], state: AgentState) -> list[StructuredTool]:
    """Wrap each BaseTool instance into a LangChain StructuredTool bound to `state`."""
    langchain_tools = []
    for tool in tools:
        adapter = _ADAPTERS.get(type(tool))
        if adapter is None:
            raise ValueError(f"No LangChain adapter registered for tool type {type(tool).__name__}")
        langchain_tools.append(adapter(tool, state))
    return langchain_tools
