# 把 Metasploit RPC 层产生的各种错误转换成 Agent 能理解的错误
# 描述错误
class MetasploitError(Exception):
    """
    Base exception.
    """

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        # 把错误信息传给父类 Exception
        super().__init__(self.message)

# ==========================================================
# RPC Exceptions
# ==========================================================
class RPCError(MetasploitError):
    """
    Raised when an RPC error occurs.
    """
    def __init__(self, message: str, method: str | None = None, details: dict | None = None):
        self.method = method
        super().__init__(message, details)
    
    def __str__(self):
        if self.method:
            return f"RPCError in method '{self.method}': {self.message}"
        return f"RPCError: {self.message}"
class RPCConnectionError(RPCError):
    """
    Raised when an RPC connection error occurs.
    """
    def __init__(self, message: str, host: str | None = None, port: int | None = None):
        self.host = host
        self.port = port
        super().__init__(message)
    
    def __str__(self):
        if self.host and self.port:
            return f"RPCConnectionError to {self.host}:{self.port}: {self.message}"
        return f"RPCConnectionError: {self.message}"

class RPCTimeoutError(RPCError):
    """
    Raised when an RPC timeout error occurs.
    """
    def __init__(self, message: str, method: str | None = None, timeout: float | None = None):
        self.timeout = timeout
        super().__init__(message, method)
    
    def __str__(self):
        if self.timeout:
            return f"RPCTimeoutError in method '{self.method}' after {self.timeout} seconds: {self.message}"
        return f"RPCTimeoutError in method '{self.method}': {self.message}"
    
# ==========================================================
# Authentication Exceptions
# ==========================================================
class AuthenticationError(MetasploitError):
    """
    Raised when an authentication error occurs.
    """
    def __init__(self, message: str, username: str | None = None, details: dict | None = None):
        self.username = username
        super().__init__(message, details)
    
    def __str__(self):
        if self.username:
            return f"AuthenticationError for user '{self.username}': {self.message}"
        return f"AuthenticationError: {self.message}"

# ==========================================================
# Module Exceptions
# ==========================================================
class ModuleError(MetasploitError):
    """
    Raised when a module error occurs.
    """
    def __init__(self, message: str, module_name: str | None = None, details: dict | None = None):
        self.module_name = module_name
        super().__init__(message, details)
    
    def __str__(self):
        if self.module_name:
            return f"ModuleError in module '{self.module_name}': {self.message}"
        return f"ModuleError: {self.message}"

class ModuleNotFoundError(ModuleError):
    """
    Raised when a module is not found.
    """
    def __init__(self, message: str, module_name: str | None = None):
        super().__init__(message, module_name)
    
    def __str__(self):
        if self.module_name:
            return f"ModuleNotFoundError: Module '{self.module_name}' not found. {self.message}"
        return f"ModuleNotFoundError: {self.message}"
    
class InvalidModuleOptionsError(ModuleError):
    """
    Raised when invalid options are provided to a module.
    """
    def __init__(self, message: str, module_name: str | None = None, invalid_options: dict | None = None):
        self.invalid_options = invalid_options or {}
        super().__init__(message, module_name)
    
    def __str__(self):
        if self.module_name:
            return f"InvalidModuleOptionsError in module '{self.module_name}': {self.message}. Invalid options: {self.invalid_options}"
        return f"InvalidModuleOptionsError: {self.message}. Invalid options: {self.invalid_options}"

class ModuleExecutionError(ModuleError):
    """
    Raised when a module execution error occurs.
    """
    def __init__(self, message: str, module_name: str | None = None, details: dict | None = None):
        super().__init__(message, module_name, details)
    
    def __str__(self):
        if self.module_name:
            return f"ModuleExecutionError in module '{self.module_name}': {self.message}. Details: {self.details}"
        return f"ModuleExecutionError: {self.message}. Details: {self.details}"

# ==========================================================
# Session Exceptions
# ==========================================================
class SessionError(MetasploitError):
    """
    Raised when a session error occurs.
    """
    def __init__(self, message: str, session_id: str | None = None, details: dict | None = None):
        self.session_id = session_id
        super().__init__(message, details)
    
    def __str__(self):
        if self.session_id:
            return f"SessionError for session '{self.session_id}': {self.message}. Details: {self.details}"
        return f"SessionError: {self.message}. Details: {self.details}"

class SessionNotFoundError(SessionError):
    """
    Raised when a session is not found.
    """
    def __init__(self, message: str, session_id: str | None = None):
        super().__init__(message, session_id)
    
    def __str__(self):
        if self.session_id:
            return f"SessionNotFoundError: Session '{self.session_id}' not found. {self.message}"
        return f"SessionNotFoundError: {self.message}"
    
class SessionClosedError(SessionError):
    """
    Raised when a session is closed unexpectedly.
    """
    def __init__(self, message: str, session_id: str | None = None):
        super().__init__(message, session_id)
    
    def __str__(self):
        if self.session_id:
            return f"SessionClosedError: Session '{self.session_id}' was closed unexpectedly. {self.message}"
        return f"SessionClosedError: {self.message}"

# ==========================================================
# Job Exceptions
# ==========================================================
class JobError(MetasploitError):
    """
    Raised when a job error occurs.
    """
    def __init__(self, message: str, job_id: str | None = None, details: dict | None = None):
        self.job_id = job_id
        super().__init__(message, details)
    
    def __str__(self):
        if self.job_id:
            return f"JobError for job '{self.job_id}': {self.message}. Details: {self.details}"
        return f"JobError: {self.message}. Details: {self.details}"

class JobNotFoundError(JobError):
    """
    Raised when a job is not found.
    """
    def __init__(self, message: str, job_id: str | None = None):
        super().__init__(message, job_id)
    
    def __str__(self):
        if self.job_id:
            return f"JobNotFoundError: Job '{self.job_id}' not found. {self.message}"
        return f"JobNotFoundError: {self.message}"

# ==========================================================
# Console Exceptions
# ==========================================================
class ConsoleError(MetasploitError):
    """
    Raised when a console error occurs.
    """
    def __init__(self, message: str, console_id: str | None = None, details: dict | None = None):
        self.console_id = console_id
        super().__init__(message, details)
    
    def __str__(self):
        if self.console_id:
            return f"ConsoleError for console '{self.console_id}': {self.message}. Details: {self.details}"
        return f"ConsoleError: {self.message}. Details: {self.details}"

# ==========================================================
# Plugins Exceptions
# ==========================================================
class PluginError(MetasploitError):
    """
    Raised when a plugin error occurs.
    """
    def __init__(self, message: str, plugin_name: str | None = None, details: dict | None = None):
        self.plugin_name = plugin_name
        super().__init__(message, details)
    
    def __str__(self):
        if self.plugin_name:
            return f"PluginError for plugin '{self.plugin_name}': {self.message}. Details: {self.details}"
        return f"PluginError: {self.message}. Details: {self.details}"

# ==========================================================
# Core Exceptions
# ==========================================================
class CoreError(MetasploitError):
    """
    Raised when a core error occurs.
    """
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details)
    
    def __str__(self):
        return f"CoreError: {self.message}. Details: {self.details}"