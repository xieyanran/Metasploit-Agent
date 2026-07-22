# Business API
# Reference https://docs.rapid7.com/metasploit/standard-api-methods-reference

from metasploit.rpc import MetasploitRPCClient
class PluginsAPI:
    def __init__(self, rpc: MetasploitRPCClient):
        self.rpc_client = rpc
    
    def load(self, plugin_name) -> dict:
        """
        Load a plugin by name.
        :param plugin_name: The name of the plugin to load.
        :return: The result of the load operation.
        """
        return self.rpc_client.call('plugin.load', plugin_name)
    
    def unload(self, plugin_name) -> dict:
        """
        Unload a plugin by name.
        :param plugin_name: The name of the plugin to unload.
        :return: The result of the unload operation.
        """
        return self.rpc_client.call('plugin.unload', plugin_name)
    
    def loaded(self) -> dict:
        """
        List all currently loaded plugins.
        :return: A dictionary containing the list of loaded plugins.
        """
        return self.rpc_client.call('plugin.loaded')
    
    
