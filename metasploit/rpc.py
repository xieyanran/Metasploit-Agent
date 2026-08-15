# https://docs.metasploit.com/docs/using-metasploit/advanced/RPC/how-to-use-metasploit-messagepack-rpc.html
# 我要如何与远程服务通信？（连接、认证、发送、接收）
# Python -> MSF RPC client（rpc.py） -> MSF RPC server -> MSF framework
# 2026-7-10 version 1.0.0

import os
import requests
import msgpack
from dotenv import load_dotenv
from metasploit.exceptions import RPCError, RPCConnectionError, RPCTimeoutError, AuthenticationError
from typing import Any, Optional

# 加载 .env 文件中的环境变量（与 core/llm.py 的 PentestAgentLLM 做法一致）
load_dotenv()

class MetasploitRPCClient:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None,
                 username: Optional[str] = None, password: Optional[str] = None):
        # Configuration parameters：显式传参优先，否则回退到 .env 里的
        # MSF_RPC_HOST/MSF_RPC_PORT/MSF_RPC_USERNAME/MSF_RPC_PASSWORD
        self.host = host or os.getenv("MSF_RPC_HOST")
        port = port if port is not None else os.getenv("MSF_RPC_PORT")
        self.port = int(port) if port is not None else None
        self.username = username or os.getenv("MSF_RPC_USERNAME")
        self.password = password or os.getenv("MSF_RPC_PASSWORD")

        if not all([self.host, self.port, self.username, self.password]):
            raise ValueError(
                "host/port/username/password 必须被提供，或在 .env 中定义 "
                "MSF_RPC_HOST/MSF_RPC_PORT/MSF_RPC_USERNAME/MSF_RPC_PASSWORD。"
            )

        # Runtime parameters
        self.token = None
        self.session = None
        self.logouttoken = None


    def login(self):
        """
          Authenticate with the Metasploit RPC server and cache the authentication token.
        """
        if self.token is not None:
            return
        
        response = self._call("auth.login", self.username, self.password)
        # print(type(response))
        # print(response)
        if response.get("result") == "success":
            self.token = response.get("token")
        else:
            raise AuthenticationError("Failed to authenticate with Metasploit RPC server: " + str(response), self.username)
    
    def logout(self):
        """
        Remove the specified token from the authentication token list. 
        """
        if self.token is None:
            return
        if self.logouttoken is None:
            return
        response = self._call("auth.logout", self.token, self.logouttoken)
        if response.get("result") == "success":
            self.token = None
        else:
            raise Exception("Failed to logout from Metasploit RPC server: " + str(response))
    
    def call(self, method: str, *params) -> Any:
        """
        Send an authenticated RPC request.
        Injects the authentication token.
        """
        if self.token is None:
            self.login()

        try:
            return self._call(method, self.token, *params)
        
        except requests.exceptions.ConnectionError as e:
            raise RPCConnectionError(
                f"Failed to connect to Metasploit RPC server at {self.host}:{self.port}: {str(e)}", self.host, self.port
            ) from e

    def _call(self, method: str, *params) -> Any:
        """
        Send a MessagePack RPC request to the Metasploit RPC server.
        examples: _post("auth.login", username, password)
        """
        if self.session is None:
            self.session = requests.Session()
        
        url = f'http://{self.host}:{self.port}/api'
        
        request_data = [method, *params]
        # print("\n!!!!!!!!!!!!")
        # print(request_data)

        try:
            response = self.session.post(
                url, 
                data=msgpack.packb(request_data), 
                headers={'Content-Type': 'binary/message-pack'},
                timeout=10,
            )

        except requests.exceptions.Timeout as e:
            raise RPCTimeoutError(
                f"RPC request to {self.host}:{self.port} timed out: {str(e)}", method, timeout=10
            ) from e

        result = _decode(msgpack.unpackb(response.content, raw=False, strict_map_key=False,))

        # print("\n!!!!!!!!!!!!")
        # print(type(result))
        # print("!!!!!!!!!!!!")
        # print(result)

        # MSF RPC 报错时返回 {"error": true, "error_message": ..., ...} 而不是
        # HTTP 错误状态码，之前没有在这里拦截，导致调用方（各 tools/builtin/*.py）
        # 拿到的是"看起来正常"的 dict，只能各自判断或干脆忽略，run_module/job_info/
        # stop_job/stop_session/shell_upgrade 等工具因此把 RPC 报错误判为成功。
        # 在这里统一拦截并抛出，交给 ToolRegistry.execute_tool 的异常兜底转换成
        # ToolResult(success=False, ...)。
        if isinstance(result, dict) and result.get("error"):
            raise RPCError(
                result.get("error_message", str(result)),
                method=method,
                details=result,
            )

        return result

def _decode(obj):
    if isinstance(obj, bytes):
        return obj.decode("utf-8")
    elif isinstance(obj, dict):
        return {_decode(k): _decode(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_decode(x) for x in obj]
    else:
        return obj