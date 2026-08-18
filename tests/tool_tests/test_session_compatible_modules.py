"""
Unit tests for SessionCompatibleModulesTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_session_compatible_modules.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.session_compatible_modules import SessionCompatibleModulesTool
from agent.state import AgentState


def test_lists_compatible_modules_for_session():
    client = MagicMock()
    client.sessions.compatible_modules.return_value = ["post/multi/manage/shell_to_meterpreter"]
    tool = SessionCompatibleModulesTool(client)

    result = tool.execute(AgentState(), session_id=1)

    assert result.success is True
    assert result.output == ["post/multi/manage/shell_to_meterpreter"]
    client.sessions.compatible_modules.assert_called_once_with(1)
