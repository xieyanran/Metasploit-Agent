"""
Unit tests for ExecuteSessionTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_execute_session.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.execute_session import ExecuteSessionTool
from agent.state import AgentState
from agent.models import Target


def test_session_not_found():
    client = MagicMock()
    client.sessions.list.return_value = {}
    tool = ExecuteSessionTool(client)

    result = tool.execute(AgentState(), session_id=1, command="whoami")

    assert result.success is False
    assert "not exit" in result.message


def test_meterpreter_session_writes_and_reads():
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "Meterpreter"}}
    client.sessions.meterpreter_read.return_value = "uid=0(root)"
    tool = ExecuteSessionTool(client)
    state = AgentState()

    result = tool.execute(state, session_id=1, command="getuid")

    assert result.success is True
    assert result.output == "uid=0(root)"
    client.sessions.meterpreter_write.assert_called_once_with(1, "getuid")
    assert state.execution.current_session == {"type": "Meterpreter"}


def test_shell_session_appends_newline_and_reads():
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "shell"}}
    client.sessions.read.return_value = "root\n"
    tool = ExecuteSessionTool(client)

    result = tool.execute(AgentState(), session_id=1, command="whoami")

    assert result.success is True
    client.sessions.write.assert_called_once_with(1, "whoami\n")
    client.sessions.read.assert_called_once_with(1, 0)


def test_protocol_specific_session_drives_console():
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "protocol-specific"}}
    client.console.create.return_value = {"id": "5"}
    client.console.read.side_effect = [
        {"data": "", "busy": False},           # after "sessions -i 1"
        {"data": "output", "busy": False},     # after the actual command
    ]
    tool = ExecuteSessionTool(client)

    result = tool.execute(AgentState(), session_id=1, command="help\n")

    assert result.success is True
    client.console.write.assert_any_call("5", "sessions -i 1\n")
    client.console.write.assert_any_call("5", "help\n")


def test_unsupported_session_type_returns_clear_error_not_typeerror():
    # Regression test: the "else" branch used to construct ToolResult without
    # the required `tool=` field, which raised TypeError and got masked by
    # the surrounding except-Exception into a confusing generic message.
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "weird-custom-type"}}
    tool = ExecuteSessionTool(client)

    result = tool.execute(AgentState(), session_id=1, command="anything")

    assert result.success is False
    assert "Unsupported session type: weird-custom-type" in result.output


def test_updates_state_target_sessions_when_target_set():
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "shell"}}
    client.sessions.read.return_value = ""
    tool = ExecuteSessionTool(client)
    state = AgentState(target=Target(address="192.168.56.101"))

    tool.execute(state, session_id=1, command="id")

    assert state.target.sessions == {1: {"type": "shell"}}


def test_exception_from_client_is_caught_and_reported():
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "Meterpreter"}}
    client.sessions.meterpreter_write.side_effect = RuntimeError("RPC connection reset")
    tool = ExecuteSessionTool(client)

    result = tool.execute(AgentState(), session_id=1, command="getuid")

    assert result.success is False
    assert "RPC connection reset" in result.message
