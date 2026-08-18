"""
Unit tests for StopJobTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_stop_job.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.stop_job import StopJobTool
from agent.state import AgentState


def test_stops_job():
    client = MagicMock()
    client.jobs.stop.return_value = {"result": "success"}
    tool = StopJobTool(client)

    result = tool.execute(AgentState(), job_id=0)

    assert result.success is True
    client.jobs.stop.assert_called_once_with(0)
