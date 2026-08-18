"""
Unit tests for CompatiblePayloadsTool. Pure mock — no live msfrpcd needed.

Run:
    pytest tests/tool_tests/test_compatible_payloads.py -v
"""
from unittest.mock import MagicMock

from tools.builtin.compatible_payloads import CompatiblePayloadsTool
from agent.state import AgentState


def test_uses_module_level_lookup_when_no_target_given():
    client = MagicMock()
    client.modules.compatible_payloads.return_value = ["payload/a"]
    tool = CompatiblePayloadsTool(client)

    result = tool.execute(AgentState(), module_name="unix/ftp/vsftpd_234_backdoor")

    assert result.success is True
    assert result.output == ["payload/a"]
    client.modules.compatible_payloads.assert_called_once_with("unix/ftp/vsftpd_234_backdoor")
    client.modules.target_compatible_payloads.assert_not_called()


def test_uses_target_scoped_lookup_when_target_given():
    client = MagicMock()
    client.modules.target_compatible_payloads.return_value = ["payload/b"]
    tool = CompatiblePayloadsTool(client)

    result = tool.execute(AgentState(), module_name="windows/smb/ms17_010_eternalblue", target=0)

    assert result.success is True
    client.modules.target_compatible_payloads.assert_called_once_with("windows/smb/ms17_010_eternalblue", 0)
    client.modules.compatible_payloads.assert_not_called()
