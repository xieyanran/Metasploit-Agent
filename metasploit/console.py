# Business API
# Reference https://docs.rapid7.com/metasploit/standard-api-methods-reference

from metasploit.rpc import MetasploitRPCClient

class ConsoleAPI:
    def __init__(self, rpc: MetasploitRPCClient):
        self.rpc_client = rpc
    
    def create(self) -> dict:
        """
        Create a new console in the Metasploit framework.
        [ "console.create", "<token>"]
        """
        return self.rpc_client.call("console.create")
    
    def destroy(self, console_id) -> dict:
        """
        Destroy a specific console in the Metasploit framework.
        [ "console.destroy", "<token>", "<ConsoleID>"]
        """
        return self.rpc_client.call("console.destroy", console_id)
    
    def list(self) -> dict:
        """
        List all consoles in the Metasploit framework.
        [ "console.list", "<token>"]
        """
        return self.rpc_client.call("console.list")
    
    def write(self, console_id, input) -> dict:
        """
        Write a command to a specific console in the Metasploit framework.
        [ "console.write", "<token>", "<ConsoleID>", "<Command>"]
        """
        return self.rpc_client.call("console.write", console_id, input)
    
    def read(self, console_id) -> dict:
        """
        Read the output of a specific console in the Metasploit framework.
        [ "console.read", "<token>", "<ConsoleID>"]
        """
        return self.rpc_client.call("console.read", console_id)
    
    def session_detach(self, console_id) -> dict:
        """
        Detach a session from a specific console in the Metasploit framework.
        [ "console.session_detach", "<token>", "<ConsoleID>"]
        """
        return self.rpc_client.call("console.session_detach", console_id)
    
    def session_kill(self, console_id) -> dict:
        """
        Kill a session from a specific console in the Metasploit framework.
        [ "console.session_kill", "<token>", "<ConsoleID>"]
        """
        return self.rpc_client.call("console.session_kill", console_id)
    
    def tabs(self, console_id, input) -> dict:
        """
        List all tabs in a specific console in the Metasploit framework.
        [ "console.tabs", "<token>", "<ConsoleID>", "<InputLine>"]
        """
        return self.rpc_client.call("console.tabs", console_id, input)