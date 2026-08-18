"""
Unit test for SetOptionTool
Run:
    pytest tests/tool_tests/test_set_option.py -v -s
"""
from unittest.mock import MagicMock

import pytest

from metasploit.client import MetasploitClient
from metasploit.client import MetasploitRPCClient
from tools.builtin.set_option import SetOptionTool
from core.scope import EngagementScope, ScopeEntry
from agent.state import AgentState


def _scope(allow_exploit=False):
    return EngagementScope(
        entries=[ScopeEntry(target="192.168.56.101", allow_exploit=allow_exploit)],
        source="test",
    )


def test_set_option_mock_rejects_unknown_option():
    client = MagicMock()
    client.modules.options.return_value = {"RHOSTS": {}, "RPORT": {}}
    tool = SetOptionTool(client, _scope())
    state = AgentState()

    result = tool.execute(
        state,
        module_type="exploit",
        module_name="exploit/unix/ftp/vsftpd_234_backdoor",
        options={"NOT_A_REAL_OPTION": "x"},
    )

    assert result.success is False
    assert "NOT_A_REAL_OPTION" in result.message
    assert state.module.options == {}


def test_set_option_mock_blocked_when_rhosts_out_of_scope():
    client = MagicMock()
    client.modules.options.return_value = {"RHOSTS": {}, "RPORT": {}}
    tool = SetOptionTool(client, _scope())

    result = tool.execute(
        AgentState(),
        module_type="exploit",
        module_name="exploit/unix/ftp/vsftpd_234_backdoor",
        options={"RHOSTS": "10.0.0.5"},
    )

    assert result.success is False
    assert "scope guard" in result.message.lower()


def test_set_option_mock_accumulates_options_across_calls():
    client = MagicMock()
    client.modules.options.return_value = {"RHOSTS": {}, "RPORT": {}}
    tool = SetOptionTool(client, _scope())
    state = AgentState()

    first = tool.execute(
        state, module_type="exploit", module_name="exploit/unix/ftp/vsftpd_234_backdoor",
        options={"RHOSTS": "192.168.56.101"},
    )
    second = tool.execute(
        state, module_type="exploit", module_name="exploit/unix/ftp/vsftpd_234_backdoor",
        options={"RPORT": 21},
    )

    assert first.success is True
    assert second.success is True
    assert state.module.options == {"RHOSTS": "192.168.56.101", "RPORT": 21}
    assert state.module.module_type == "exploit"


def test_set_option_mock_merges_payload_options_for_validation():
    client = MagicMock()
    # module.options() only knows about the exploit's own options; PAYLOAD's
    # LHOST/LPORT only show up once we also query "payload" options, which
    # SetOptionTool is responsible for merging in before validating.
    client.modules.options.side_effect = lambda module_type, module_name: (
        {"RHOSTS": {}} if module_type != "payload" else {"LHOST": {}, "LPORT": {}}
    )
    tool = SetOptionTool(client, _scope())
    state = AgentState()

    result = tool.execute(
        state,
        module_type="exploit",
        module_name="exploit/unix/ftp/vsftpd_234_backdoor",
        options={"PAYLOAD": "cmd/unix/interact", "LHOST": "192.168.56.1"},
    )

    assert result.success is True
    assert state.module.payload == "cmd/unix/interact"


@pytest.mark.integration
def test_set_option():
    rpc_client = MetasploitRPCClient(
        host="127.0.0.1",
        port=55553,
        username="msf",
        password="123456",
    )

    rpc_client.login()

    client = MetasploitClient(rpc_client)
    scope = EngagementScope(entries=[ScopeEntry(target="127.0.0.1")], source="test")
    tool = SetOptionTool(client=client, scope=scope)

    state = AgentState()

    result = tool.execute(
        state=state,
        module_type="exploit",
        module_name="exploit/unix/ftp/vsftpd_234_backdoor",
        options={"RHOSTS": "127.0.0.1"},
    )

    assert result.success is True
    assert state.module.options == {"RHOSTS": "127.0.0.1"}

    print("\nSet Option:", result.output)

