# Business API
# Reference https://docs.rapid7.com/metasploit/standard-api-methods-reference

from metasploit.rpc import MetasploitRPCClient
class ModulesAPI:
    def __init__(self, rpc: MetasploitRPCClient):
        self.rpc_client = rpc
    
    def exploits(self) -> dict:
        """
        List all loaded exploit modules in the Metasploit framework.
        [ "module.exploits", "<token>"]
        """
        return self.rpc_client.call("module.exploits")
    
    def auxiliary(self) -> dict:
        """
        List all loaded auxiliary modules in the Metasploit framework.
        [ "module.auxiliary", "<token>"]
        """
        return self.rpc_client.call("module.auxiliary")
    
    def post(self) -> dict:
        """
        List all loaded post modules in the Metasploit framework.
        [ "module.post", "<token>"]
        """
        return self.rpc_client.call("module.post")
    
    def payloads(self) -> dict:
        """
        List all loaded payload modules in the Metasploit framework.
        [ "module.payloads", "<token>"]
        """
        return self.rpc_client.call("module.payloads")
    
    def encoders(self) -> dict:
        """
        List all loaded encoder modules in the Metasploit framework.
        [ "module.encoders", "<token>"]
        """
        return self.rpc_client.call("module.encoders")
    
    def nops(self) -> dict:
        """
        List all loaded nop modules in the Metasploit framework.
        [ "module.nops", "<token>"]
        """
        return self.rpc_client.call("module.nops")

    def search(self, query: str) -> list[dict]:
        """
        Search Metasploit modules.
        ["modules.search", "<token>", {"keywords": [query]}]
        """
        return self.rpc_client.call("module.search", query)
    
    def info(self, module_type, module_name) -> dict:
        """
        Get information about a specific module in the Metasploit framework.
        [ "module.info", "<token>", "<ModuleType>", "<ModuleName>"]
        """
        return self.rpc_client.call("module.info", module_type, module_name)

    def options(self, module_type, module_name) -> dict:
        """
        ["module.options", "<token>", "<ModuleType>", "<ModuleName>"]
        """
        return self.rpc_client.call("module.options", module_type, module_name)

    def compatible_payloads(self, module_name) -> dict:
        """
        Get a list of compatible payloads for a specific module in the Metasploit framework.
        [ "module.compatible_payloads", "<token>", "<ModuleName>"]
        """
        return self.rpc_client.call("module.compatible_payloads", module_name)
    
    def target_compatible_payloads(self, module_name, target) -> dict:
        """
        Get a list of compatible payloads for a specific module and target in the Metasploit framework.
        [ "module.target_compatible_payloads", "<token>", "<ModuleName>", "<Target>"]
        """
        return self.rpc_client.call("module.target_compatible_payloads", module_name, target)
    
    def compatible_sessions(self, module_name) -> dict:
        """
        Get a list of compatible sessions for a specific module in the Metasploit framework.
        [ "module.compatible_sessions", "<token>", "<ModuleName>"]
        """
        return self.rpc_client.call("module.compatible_sessions", module_name)
    
    def encode(self, data, encoder_module, options) -> dict:
        """
        Encode a payload using a specific encoder module in the Metasploit framework.
        [ "module.encode", "<token>", "Data", "EncoderModule", "Options"]
        """
        return self.rpc_client.call("module.encode", data, encoder_module, options)
    
    def execute(self, module_type, module_name, options) -> dict:
        """
        Execute a specific module with the given options in the Metasploit framework.
        [ "module.execute", "<token>", "<ModuleType>", "<ModuleName>", "<Options>"]
        """
        return self.rpc_client.call("module.execute", module_type, module_name, options)