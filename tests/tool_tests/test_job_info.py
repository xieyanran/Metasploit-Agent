"""
Unit tests for JobInfoTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_job_info.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.job_info import JobInfoTool
from agent.state import AgentState


def test_returns_job_info():
    client = MagicMock()
    client.jobs.info.return_value = {"jid": 0, "name": "Exploit: multi/handler"}
    tool = JobInfoTool(client)

    result = tool.execute(AgentState(), job_id=0)

    assert result.success is True
    client.jobs.info.assert_called_once_with(0)
