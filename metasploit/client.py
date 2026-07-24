# Facade Pattern
# 
from metasploit.core import CoreAPI
from metasploit.modules import ModulesAPI
from metasploit.sessions import SessionsAPI
from metasploit.job import JobAPI
from metasploit.sessions import SessionsAPI
from metasploit.plugins import PluginsAPI
from metasploit.console import ConsoleAPI
from metasploit.rpc import MetasploitRPCClient


class MetasploitClient:
    def __init__(self, rpc: MetasploitRPCClient):
        self._rpc = rpc
        self.core = CoreAPI(rpc)
        self.modules = ModulesAPI(rpc)
        self.sessions = SessionsAPI(rpc)
        self.jobs = JobAPI(rpc)
        self.plugins = PluginsAPI(rpc)
        self.console = ConsoleAPI(rpc)

    