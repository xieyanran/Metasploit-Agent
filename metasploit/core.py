# Business API
# Reference https://docs.rapid7.com/metasploit/standard-api-methods-reference

from metasploit.rpc import MetasploitRPCClient
class CoreAPI:
    def __init__(self, rpc: MetasploitRPCClient):
        self.rpc_client = rpc

    def version(self) -> dict:
        """
        Get the version of the Metasploit framework.
        [ "core.version", "<token>"]
        """
        return self.rpc_client.call("core.version")
    
    def stop(self) -> dict:
        """
        Stop the Metasploit framework.
        [ "core.stop", "<token>"]
        """
        return self.rpc_client.call("core.stop")
    
    def thread_list(self) -> dict:
        """
        List all threads in the Metasploit framework.
        [ "core.thread_list", "<token>"]
        """
        return self.rpc_client.call("core.thread_list")
    
    def thread_kill(self, thread_id) -> dict:
        """
        Kill a specific thread in the Metasploit framework.
        [ "core.thread.kill", "<token>", "<ThreadID>"]
        """
        return self.rpc_client.call("core.thread.kill", thread_id) 
    
    def setg(self, option_name, option_value) -> dict:
        """
        Set a global variable in the Metasploit framework.
        [ "core.setg", "<token>", "<OptionName>", "<OptionValue>"]
        """
        return self.rpc_client.call("core.setg", option_name, option_value)
    
    def unsetg(self, option_name) -> dict:
        """
        Unset a global variable in the Metasploit framework.
        [ "core.unsetg", "<token>", "<OptionName>"]
        """
        return self.rpc_client.call("core.unsetg", option_name)
    
    def save(self) -> dict:
        """
        Save the current state of the Metasploit framework,typically in ~/.msf3/config. 
        [ "core.save", "<token>"]
        """
        return self.rpc_client.call("core.save")

    def add_module_path(self, path) -> dict:    
        """
        Add a module path to the Metasploit framework.
        [ "core.add_module_path", "<token>", "<Path>"]
        """
        return self.rpc_client.call("core.add_module_path", path)
    
    def module_stats(self) -> dict:
        """
        Returns the number of modules loaded, broken down by type.
        [ "core.module_stats", "<token>"]
        """
        return self.rpc_client.call("core.module_stats")
    
    def reload_modules(self) -> dict:
        """
        Reload all modules in the Metasploit framework. This is the only way to purge a previously loaded module that the caller would like to remove. This method can take a long time to return, up to a minute on slow servers.
        [ "core.reload_modules", "<token>"]
        """
        return self.rpc_client.call("core.reload_modules")
