"""
Tool for searching Metasploit modules
"""
from tools.base import BaseTool
from metasploit.client import MetasploitClient
from agent.state import AgentState
from agent.models import ToolResult

class SearchModuleTool(BaseTool):
    """Search Metasploit modules by keyword."""

    name = "search_module"
    description = "Search Metasploit modules."

    def __init__(self, client: MetasploitClient):
       self.client = client

    def execute(self, 
                state: AgentState,
                query: str,
                ) -> ToolResult:
        modules = self.client.modules.search (query = query)
        # print("\n!!!!!!!!!!")
        # print("modules:", modules)

        return ToolResult(
            tool = f"Search Metaspolit Module",
            success = True,
            output = modules,
            message = f"Keyword searched successfully.",
        )
        
