"""
Entry point for firstpentestAgent.

这个文件负责：
  1. 连接 Metasploit RPC（需要提前在 msfconsole 里执行
     `load msgrpc ServerHost=127.0.0.1 ServerPort=55552 User=msf Pass=123456 SSL=false`）
  2. 注册所有 agent/tools/ 下的工具到 ToolRegistry
  3. 把它们包装成 LangChain 工具（agent/langchain_tools.py），
     绑定同一个 AgentState
  4. 用 langchain.agents.create_agent 跑 ReAct 循环
     （取代了原来手写的 agent/reasoning + agent/llm）

运行前需要：
  pip install -r requirements.txt
  export OPENAI_API_KEY=sk-xxx
  export MSF_RPC_HOST=127.0.0.1
  export MSF_RPC_PORT=55552
  export MSF_RPC_USER=xxx
  export MSF_RPC_PASS=xxx
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from metasploit.rpc import MetasploitRPCClient
from metasploit.client import MetasploitClient

from agent.state import AgentState
from agent.models import Target
from agent.tool_registry import ToolRegistry
from agent.langchain_tools import build_langchain_tools

from agent.tools.nmap_scan import NmapScanTool
from agent.tools.search_module import SearchModuleTool
from agent.tools.get_module_info import InfoModuleTool
from agent.tools.show_option import ShowOptionTool
from agent.tools.set_option import SetOptionTool
from agent.tools.run_module import RunModuleTool
from agent.tools.list_sessions import ListSessionTool
from agent.tools.execute_session import ExecuteSessionTool
from agent.tools.kill_meterpreter_session import KillMeterpreterSessionTool

SYSTEM_PROMPT = "You are a professional penetration tester."


def target_from_url(url: str) -> Target:
    """
    nmap/db_nmap scans a host, not a full URL, so strip the scheme,
    path, query string, etc. and keep just the hostname.
    e.g. "https://example.com:8443/login?x=1" -> "example.com"
    """
    hostname = urlparse(url).hostname
    if not hostname:
        raise ValueError(f"Could not extract a hostname from '{url}'")
    return Target(address=hostname, description=url)


def build_metasploit_client() -> MetasploitClient:
    rpc = MetasploitRPCClient(
        host=os.environ.get("MSF_RPC_HOST", "127.0.0.1"),
        port=int(os.environ.get("MSF_RPC_PORT", "55552")),
        username=os.environ.get("MSF_RPC_USER", "msf"),
        password=os.environ.get("MSF_RPC_PASS", "123456"),
    )
    return MetasploitClient(rpc)


def build_tool_registry(client: MetasploitClient) -> ToolRegistry:
    registry = ToolRegistry()
    for tool_cls in (
        NmapScanTool,
        SearchModuleTool,
        InfoModuleTool,
        ShowOptionTool,
        SetOptionTool,
        RunModuleTool,
        ListSessionTool,
        ExecuteSessionTool,
        KillMeterpreterSessionTool,
    ):
        registry.register(tool_cls(client))
    return registry


def main():
    client = build_metasploit_client()
    registry = build_tool_registry(client)

    state = AgentState()
    # TODO: 在这里给 state.target 设一个真实的 agent.models.Target(...)
    # 否则工具里依赖 state.target 的部分（比如 list_session/execute_session）拿不到目标。
    state.target = target_from_url(os.environ.get("TARGET_URL", "https://example.com"))

    tools = build_langchain_tools(registry.all(), state)

    model = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )
    agent = create_agent(model, tools, system_prompt=SYSTEM_PROMPT)

    goal = os.environ.get(
        "AGENT_GOAL",
        f"Assess {state.target.address} and report what you find.",
    )
    result = agent.invoke({"messages": [HumanMessage(content=goal)]})

    for message in result["messages"]:
        print(f"[{message.type}] {message.content}")


if __name__ == "__main__":
    main()
