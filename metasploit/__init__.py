"""
Metasploit Python SDK
A lightweight Python client for the Metasploit MessagePack RPC API.
"""

__version__ = "1.0.0"

from metasploit.client import MetasploitClient
from metasploit.rpc import MetasploitRPCClient
from metasploit.exceptions import (
    MetasploitError,
    RPCError,
    RPCConnectionError,
    RPCTimeoutError,
    AuthenticationError,
    ModuleError,
    ModuleNotFoundError,
    InvalidModuleOptionsError,
    ModuleExecutionError,
    SessionError,
    SessionNotFoundError,
    SessionClosedError,
    JobError,
    JobNotFoundError,
    ConsoleError,
    PluginError,
    CoreError,
)

__all__ = [

    "MetasploitClient",
    "MetasploitRPCClient",
    "MetasploitError",
    "RPCError",
    "RPCConnectionError",
    "RPCTimeoutError",
    "AuthenticationError",
    "ModuleError",
    "ModuleNotFoundError",
    "InvalidModuleOptionsError",
    "ModuleExecutionError",
    "SessionError",
    "SessionNotFoundError",
    "SessionClosedError",
    "JobError",
    "JobNotFoundError",
    "ConsoleError",
    "PluginError",
    "CoreError",
]

