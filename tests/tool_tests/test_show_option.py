"""
Unit test for ShowOptionTool
Run:
    pytest tests/tool_tests/test_show_option.py -v -s
"""
from unittest.mock import MagicMock

import pytest

from metasploit.client import MetasploitClient
from metasploit.client import MetasploitRPCClient
from tools.builtin.show_option import ShowOptionTool
from agent.state import AgentState


def test_show_option_mock():
    client = MagicMock()
    client.modules.options.return_value = {"RHOSTS": {"required": True}, "RPORT": {"required": True}}
    tool = ShowOptionTool(client=client)

    result = tool.execute(
        state=AgentState(),
        module_type="exploit",
        module_name="exploit/unix/ftp/vsftpd_234_backdoor",
    )

    assert result.success is True
    assert "RHOSTS" in result.output


@pytest.mark.integration
def test_show_option():
    rpc_client = MetasploitRPCClient(
                    host="127.0.0.1",
                    port=55553,
                    username="msf",
                    password="123456",
                )

    rpc_client.login()

    client = MetasploitClient(rpc_client)

    tool = ShowOptionTool(client=client)

    state = AgentState()

    result = tool.execute(
        state = state,
        module_type = "exploit",
        module_name = "exploit/unix/ftp/vsftpd_234_backdoor",
    )

    assert result.success is True
    assert result.output is not None
    assert isinstance(result.output, dict)
        
    print("\nOption Info:", result.output)

