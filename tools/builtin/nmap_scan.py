"""
Tool for running Nmap scans through Metasploit's db_nmap console command
to discover open ports and services on a target.
"""
import re
import time

from typing import List

from tools.base import BaseTool, ToolParameter
from metasploit.client import MetasploitClient
from core.scope import EngagementScope
from agent.state import AgentState
from agent.models import ToolResult

# db_nmap runs inside the msfconsole console, so the string we write is a
# console command line, not a shell command. Still, block characters that
# could terminate the nmap args and inject a second console command.
_UNSAFE_CHARS = re.compile(r"[;\n\r`|$]")

_DEFAULT_OPTIONS = "-sV"
_POLL_INTERVAL = 1.0
_MAX_WAIT_SECONDS = 300


class NmapScanTool(BaseTool):
    """
    Run `db_nmap` inside Metasploit to scan a target for open ports and
    services. Results are imported into the Metasploit database as a
    side effect of db_nmap (as opposed to `nmap`, which would not).
    """

    name = "nmap_scan"
    description = "Scan a target with Nmap via Metasploit (db_nmap) to discover open ports and services."

    def __init__(self, client: MetasploitClient, scope: EngagementScope, name: str = "nmap_scan", description: str = "Scan a target with Nmap via Metasploit (db_nmap) to discover open ports and services."):
        self.client = client
        self.scope = scope
        self.name = name
        self.description = description

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="target", type="string", description="Scan target (host or CIDR range)."),
            ToolParameter(name="options", type="string", description="Nmap options.", required=False, default=_DEFAULT_OPTIONS),
        ]

    def execute(
        self,
        state: AgentState,
        target: str,
        options: str = _DEFAULT_OPTIONS,
    ) -> ToolResult:
        if not target or _UNSAFE_CHARS.search(target):
            return ToolResult(
                tool="nmap_scan",
                success=False,
                output=None,
                message="Invalid target.",
            )

        if _UNSAFE_CHARS.search(options):
            return ToolResult(
                tool="nmap_scan",
                success=False,
                output=None,
                message="Invalid options.",
            )

        violation = self.scope.authorize(target, tool_name=self.name)
        if violation:
            return ToolResult(
                tool="nmap_scan",
                success=False,
                output=None,
                message=f"Blocked by scope guard: {violation}",
            )

        console = self.client.console.create()
        console_id = console["id"]

        try:
            self.client.console.write(
                console_id, f"db_nmap {options} {target}\n"
            )

            output = ""
            waited = 0.0
            while waited < _MAX_WAIT_SECONDS:
                time.sleep(_POLL_INTERVAL)
                waited += _POLL_INTERVAL

                result = self.client.console.read(console_id)
                output += result.get("data", "")

                if not result.get("busy", False):
                    break
            else:
                return ToolResult(
                    tool="nmap_scan",
                    success=False,
                    output=output,
                    message=f"Nmap scan on '{target}' timed out after {_MAX_WAIT_SECONDS}s.",
                )

            return ToolResult(
                tool="nmap_scan",
                success=True,
                output=output,
                message=f"Nmap scan on '{target}' completed successfully.",
            )

        finally:
            self.client.console.destroy(console_id)
