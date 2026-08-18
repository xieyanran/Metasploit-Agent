import pytest

from metasploit.client import MetasploitRPCClient

@pytest.mark.integration
def test_login():
    client = MetasploitRPCClient(
        host="127.0.0.1",
        port=55553,
        username="msf",
        password="123456",
    )

    client.login()

    assert client.token is not None