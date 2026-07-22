# Business API
# Reference https://docs.rapid7.com/metasploit/standard-api-methods-reference

from metasploit.rpc import MetasploitRPCClient
class SessionsAPI:
    def __init__(self, rpc: MetasploitRPCClient):
        self.rpc_client = rpc
    
    def list(self) -> dict:
        """
        List all active sessions.
        [ "session.list", "<token>" ]
        """
        return self.rpc_client.call('session.list')
    
    def stop(self, session_id) -> dict:
        """
        Stop a session by ID.
        [ "session.stop", "<token>", "SessionID" ]
        """
        return self.rpc_client.call('session.stop', session_id)
    
    def read(self, session_id, read_pointer) -> dict:
        """
        Read data from a shell session.
        [ "session.shell_read", "<token>", "SessionID", "ReadPointer ]
        """
        return self.rpc_client.call('session.shell_read', session_id, read_pointer)
    
    def write(self, session_id, id) -> dict:
        """
        Write data to a shell session.
        [ "session.shell_write", "<token>", "SessionID", "id\n" ]
        """
        return self.rpc_client.call('session.shell_write', session_id, id)
    
    def meterpreter_write(self, session_id, command) -> dict:
        """
        Write data to a meterpreter session.
        [ "session.meterpreter_write", "<token>", "SessionID", "ps" ]
        """
        return self.rpc_client.call('session.meterpreter_write', session_id, command)
    
    def meterpreter_read(self, session_id) -> dict:
        """
        Read data from a meterpreter session.
        [ "session.meterpreter_read", "<token>"]
        """
        return self.rpc_client.call('session.meterpreter_read', session_id)
    
    def meterpreter_run_single(self, session_id, command) -> dict:
        """
        Run a single command in a meterpreter session.
        [ "session.meterpreter_run_single", "<token>", "SessionID", "ps" ]
        """
        return self.rpc_client.call('session.meterpreter_run_single', session_id, command)
    
    def meterpreter_script(self, session_id, script_name) -> dict:
        """
        Run a meterpreter script with arguments.
        ["session.meterpreter_script","<token>","SessionID","scriptname"]
        """
        return self.rpc_client.call('session.meterpreter_script', session_id, script_name)
    
    def meterpreter_session_detach(self, session_id) -> dict:
        """
        Detach a meterpreter session.
        [ "session.meterpreter_session_detach", "<token>", "SessionID" ]
        """
        return self.rpc_client.call('session.meterpreter_session_detach', session_id)
    
    def meterpreter_session_kill(self, session_id) -> dict:
        """
        Kill a meterpreter session.
        [ "session.meterpreter_session_kill", "<token>", "SessionID" ]
        """
        return self.rpc_client.call('session.meterpreter_session_kill', session_id)
    
    def meterpreter_tabs (self, session_id, input) -> dict:
        """
        Get tab completion for a meterpreter command.
        [ "session.meterpreter_tabs", "<token>", "SessionID", "InputLine"]
        """
        return self.rpc_client.call('session.meterpreter_tabs', session_id, input)
    
    def compatible_modules(self, session_id) -> dict:
        """
        List compatible modules for a session.
        [ "session.compatible_modules", "<token>", "SessionID" ]
        """
        return self.rpc_client.call('session.compatible_modules', session_id)
    
    def shell_upgrade(self, session_id, lhost, lport) -> dict:
        """
        Upgrade a shell session to a meterpreter session.
        [ "session.shell_upgrade", "<token>", "SessionID", "1.2.3.4", 4444 ]
        """
        return self.rpc_client.call('session.shell_upgrade', session_id, lhost, lport)
    
    def ring_clear(self, session_id) -> dict:
        """
        Clear the ring buffer for a session.
        [ "session.ring_clear", "<token>", "SessionID" ]
        """
        return self.rpc_client.call('session.ring_clear', session_id)
    
    def ring_last(self, session_id) -> dict:
        """
        Get the last entry in the ring buffer for a session.
        [ "session.ring_last", "<token>", "SessionID" ]
        """
        return self.rpc_client.call('session.ring_last', session_id)
    
    def ring_put(self, session_id, data) -> dict:
        """
        Add an entry to the ring buffer for a session.
        [ "session.ring_put", "<token>", "SessionID", "id\n" ]
        """
        return self.rpc_client.call('session.ring_put', session_id, data)

    