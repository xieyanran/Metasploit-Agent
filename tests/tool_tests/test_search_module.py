"""
Unit test for SearchModuleTool
Run:
    pytest tests/tool_tests/test_search_module.py -v
"""
from unittest.mock import MagicMock

import pytest

from metasploit.client import MetasploitClient
from metasploit.client import MetasploitRPCClient
from tools.builtin.search_module import SearchModuleTool
from agent.state import AgentState


def test_search_module_mock():
    client = MagicMock()
    client.modules.search.return_value = [{"name": "vsftpd_234_backdoor"}]
    tool = SearchModuleTool(client=client)

    result = tool.execute(state=AgentState(), query="vsftpd")

    assert result.success is True
    assert result.output == [{"name": "vsftpd_234_backdoor"}]
    client.modules.search.assert_called_once_with(query="vsftpd")


@pytest.mark.integration
def test_search_module():
    rpc_client = MetasploitRPCClient(
            host="127.0.0.1",
            port=55553,
            username="msf",
            password="123456",
        )
    
    rpc_client.login()

    client = MetasploitClient(rpc_client)

    tool = SearchModuleTool(client=client)

    state = AgentState()

    result = tool.execute(
        state = state,
        query = "vsftpd",
    )

    assert result.success is True
    assert result.output is not None
    assert isinstance(result.output, list)

    print("\nSearch Results:", result.output)



