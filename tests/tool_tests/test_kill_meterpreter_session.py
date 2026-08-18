"""
Unit tests for KillMeterpreterSessionTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_kill_meterpreter_session.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.kill_meterpreter_session import KillMeterpreterSessionTool
from agent.state import AgentState


def test_session_not_found():
    client = MagicMock()
    client.sessions.list.return_value = {}
    tool = KillMeterpreterSessionTool(client)

    result = tool.execute(AgentState(), session_id=99)

    assert result.success is False
    client.sessions.meterpreter_session_kill.assert_not_called()


def test_rejects_non_meterpreter_session():
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "shell"}}
    tool = KillMeterpreterSessionTool(client)

    result = tool.execute(AgentState(), session_id=1)

    assert result.success is False
    client.sessions.meterpreter_session_kill.assert_not_called()


def test_kills_meterpreter_session():
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "Meterpreter"}}
    client.sessions.meterpreter_session_kill.return_value = {"result": "success"}
    tool = KillMeterpreterSessionTool(client)

    result = tool.execute(AgentState(), session_id=1)

    assert result.success is True
    client.sessions.meterpreter_session_kill.assert_called_once_with(1)


def test_session_id_lookup_falls_back_to_string_key():
    # msfrpcd returns session ids as msgpack keys that can decode as either
    # int or str depending on payload; execute_session/kill both guard for it.
    client = MagicMock()
    client.sessions.list.return_value = {"1": {"type": "Meterpreter"}}
    tool = KillMeterpreterSessionTool(client)

    result = tool.execute(AgentState(), session_id=1)

    assert result.success is True
