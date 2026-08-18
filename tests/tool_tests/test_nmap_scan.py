"""
Unit tests for NmapScanTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_nmap_scan.py -v
"""
from unittest.mock import MagicMock, patch

from tools.builtin.nmap_scan import NmapScanTool
from core.scope import EngagementScope, ScopeEntry
from agent.state import AgentState


def make_tool(tmp_path, allowed=True):
    client = MagicMock()
    entries = [ScopeEntry(target="192.168.56.101")] if allowed else []
    scope = EngagementScope(entries=entries, source="test", audit_log_path=tmp_path / "audit.log")
    return NmapScanTool(client, scope), client


def test_rejects_unsafe_target_chars(tmp_path):
    tool, client = make_tool(tmp_path)
    result = tool.execute(AgentState(), target="192.168.56.101; rm -rf /")
    assert result.success is False
    client.console.create.assert_not_called()


def test_rejects_unsafe_options_chars(tmp_path):
    tool, client = make_tool(tmp_path)
    result = tool.execute(AgentState(), target="192.168.56.101", options="-sV `whoami`")
    assert result.success is False
    client.console.create.assert_not_called()


def test_blocked_by_scope_guard_before_touching_client(tmp_path):
    tool, client = make_tool(tmp_path, allowed=False)
    result = tool.execute(AgentState(), target="192.168.56.101")
    assert result.success is False
    assert "scope guard" in result.message.lower()
    client.console.create.assert_not_called()


def test_happy_path_polls_until_not_busy(tmp_path):
    tool, client = make_tool(tmp_path)
    client.console.create.return_value = {"id": "1"}
    client.console.read.side_effect = [
        {"data": "Starting Nmap...\n", "busy": True},
        {"data": "Nmap scan report...\n", "busy": False},
    ]

    with patch("tools.builtin.nmap_scan.time.sleep"):
        result = tool.execute(AgentState(), target="192.168.56.101")

    assert result.success is True
    assert "Starting Nmap" in result.output
    assert "Nmap scan report" in result.output
    client.console.destroy.assert_called_once_with("1")


def test_times_out_if_console_stays_busy(tmp_path):
    tool, client = make_tool(tmp_path)
    client.console.create.return_value = {"id": "1"}
    client.console.read.return_value = {"data": "", "busy": True}

    with patch("tools.builtin.nmap_scan.time.sleep"):
        result = tool.execute(AgentState(), target="192.168.56.101")

    assert result.success is False
    assert "timed out" in result.message
    client.console.destroy.assert_called_once_with("1")
