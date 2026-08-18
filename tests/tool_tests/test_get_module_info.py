"""
Unit test for InfoModuleTool
Run:
    pytest tests/tool_tests/test_get_module_info.py -v -s
"""
from unittest.mock import MagicMock

import pytest

from metasploit.client import MetasploitClient
from metasploit.client import MetasploitRPCClient
from tools.builtin.get_module_info import InfoModuleTool
from agent.state import AgentState


def test_get_module_info_mock():
    client = MagicMock()
    client.modules.info.return_value = {"name": "VSFTPD v2.3.4 Backdoor Command Execution"}
    tool = InfoModuleTool(client=client)

    result = tool.execute(
        state=AgentState(),
        module_type="exploit",
        module_name="exploit/unix/ftp/vsftpd_234_backdoor",
    )

    assert result.success is True
    assert result.output["name"] == "VSFTPD v2.3.4 Backdoor Command Execution"
    client.modules.info.assert_called_once_with(
        module_type="exploit", module_name="exploit/unix/ftp/vsftpd_234_backdoor"
    )


@pytest.mark.integration
def test_get_module_info():
    rpc_client = MetasploitRPCClient(
                host="127.0.0.1",
                port=55553,
                username="msf",
                password="123456",
            )

    rpc_client.login()

    client = MetasploitClient(rpc_client)

    tool = InfoModuleTool(client=client)

    state = AgentState()

    result = tool.execute(
        state = state,
        module_type = "exploit",
        # Not Full name, just name!
        module_name = "exploit/unix/ftp/vsftpd_234_backdoor",
    )

    assert result.success is True
    assert result.output is not None
    assert isinstance(result.output, dict)
    
    print("\nModule Info:", result.output)