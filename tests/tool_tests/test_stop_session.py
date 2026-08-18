"""
Unit tests for StopSessionTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_stop_session.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.stop_session import StopSessionTool
from agent.state import AgentState


def test_stops_session():
    client = MagicMock()
    client.sessions.stop.return_value = {"result": "success"}
    tool = StopSessionTool(client)

    result = tool.execute(AgentState(), session_id=1)

    assert result.success is True
    client.sessions.stop.assert_called_once_with(1)
