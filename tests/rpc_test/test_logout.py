import pytest

from metasploit.client import MetasploitRPCClient

@pytest.mark.integration
def test_logout():
    # `logout()` is a no-op unless we're actually logged in first (see
    # MetasploitRPCClient.logout: it returns early when self.token is None),
    # so this needs a real login beforehand or the assertion below is
    # trivially true regardless of whether logout works.
    client = MetasploitRPCClient(
        host="127.0.0.1",
        port=55553,
        username="msf",
        password="123456",
    )

    client.login()
    assert client.token is not None

    client.logout()

    assert client.token is None