"""
Unit test for RunModuleTool
Run:
    pytest tests/tool_tests/test_run_module.py -v -s
"""
from unittest.mock import MagicMock

import pytest

from metasploit.client import MetasploitClient
from metasploit.client import MetasploitRPCClient
from tools.builtin.run_module import RunModuleTool
from core.scope import EngagementScope, ScopeEntry
from agent.state import AgentState


def test_run_module_mock_auxiliary_in_scope():
    client = MagicMock()
    client.modules.execute.return_value = {"job_id": 1}
    scope = EngagementScope(entries=[ScopeEntry(target="192.168.56.101")], source="test")
    tool = RunModuleTool(client=client, scope=scope)

    result = tool.execute(
        AgentState(),
        module_type="auxiliary",
        module_name="auxiliary/scanner/http/http_version",
        options={"RHOSTS": "192.168.56.101", "RPORT": 80},
    )

    assert result.success is True
    client.modules.execute.assert_called_once_with(
        module_type="auxiliary",
        module_name="auxiliary/scanner/http/http_version",
        options={"RHOSTS": "192.168.56.101", "RPORT": 80},
    )


def test_run_module_mock_blocked_when_target_out_of_scope():
    client = MagicMock()
    scope = EngagementScope(entries=[ScopeEntry(target="192.168.56.101")], source="test")
    tool = RunModuleTool(client=client, scope=scope)

    result = tool.execute(
        AgentState(),
        module_type="auxiliary",
        module_name="auxiliary/scanner/http/http_version",
        options={"RHOSTS": "10.0.0.5", "RPORT": 80},
    )

    assert result.success is False
    assert "scope guard" in result.message.lower()
    client.modules.execute.assert_not_called()


def test_run_module_mock_exploit_blocked_without_allow_exploit():
    client = MagicMock()
    scope = EngagementScope(
        entries=[ScopeEntry(target="192.168.56.101", allow_exploit=False)], source="test"
    )
    tool = RunModuleTool(client=client, scope=scope)

    result = tool.execute(
        AgentState(),
        module_type="exploit",
        module_name="exploit/unix/ftp/vsftpd_234_backdoor",
        options={"RHOSTS": "192.168.56.101"},
    )

    assert result.success is False
    assert "exploit" in result.message.lower()
    client.modules.execute.assert_not_called()


def test_run_module_mock_exploit_allowed_with_allow_exploit():
    client = MagicMock()
    client.modules.execute.return_value = {"job_id": 2}
    scope = EngagementScope(
        entries=[ScopeEntry(target="192.168.56.101", allow_exploit=True)], source="test"
    )
    tool = RunModuleTool(client=client, scope=scope)

    result = tool.execute(
        AgentState(),
        module_type="exploit",
        module_name="exploit/unix/ftp/vsftpd_234_backdoor",
        options={"RHOSTS": "192.168.56.101"},
    )

    assert result.success is True
    client.modules.execute.assert_called_once()


@pytest.mark.integration
def test_run_module():
    rpc_client = MetasploitRPCClient(
                    host="127.0.0.1",
                    port=55553,
                    username="msf",
                    password="123456",
                )

    rpc_client.login()

    client = MetasploitClient(rpc_client)

    # auxiliary/scanner module, no exploit-class execution -> allow_exploit
    # doesn't need to be set for 127.0.0.1 here.
    scope = EngagementScope(entries=[ScopeEntry(target="127.0.0.1")], source="test")

    tool = RunModuleTool(client=client, scope=scope)
    
    state = AgentState()

    result = tool.execute(
        state = state,
        # easy to test
        module_type="auxiliary",
        module_name="auxiliary/scanner/http/http_version",
        options={
        "RHOSTS": "127.0.0.1",
        "RPORT": 80,
        }
    )

    assert result.success is True
    assert result.output is not None
    assert isinstance(result.output, dict)
        
    print("\nRun Module:", result.output)