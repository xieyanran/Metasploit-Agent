"""
Unit tests for ListSessionTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_list_sessions.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.list_sessions import ListSessionTool
from agent.state import AgentState
from agent.models import Target


def test_lists_sessions_from_client():
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "shell"}}
    tool = ListSessionTool(client)

    result = tool.execute(AgentState())

    assert result.success is True
    assert result.output == {1: {"type": "shell"}}


def test_updates_state_target_sessions_when_target_set():
    client = MagicMock()
    client.sessions.list.return_value = {1: {"type": "shell"}}
    tool = ListSessionTool(client)
    state = AgentState(target=Target(address="192.168.56.101"))

    tool.execute(state)

    assert state.target.sessions == {1: {"type": "shell"}}


def test_does_not_touch_target_when_none():
    client = MagicMock()
    client.sessions.list.return_value = {}
    tool = ListSessionTool(client)
    state = AgentState()

    result = tool.execute(state)

    assert result.success is True
    assert state.target is None
