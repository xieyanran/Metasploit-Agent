"""
Unit tests for ListJobsTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_list_jobs.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.list_jobs import ListJobsTool
from agent.state import AgentState


def test_lists_jobs_from_client():
    client = MagicMock()
    client.jobs.list.return_value = {"0": "Exploit: multi/handler"}
    tool = ListJobsTool(client)

    result = tool.execute(AgentState())

    assert result.success is True
    assert result.output == {"0": "Exploit: multi/handler"}
