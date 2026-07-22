# https://docs.metasploit.com/docs/using-metasploit/advanced/RPC/how-to-use-metasploit-messagepack-rpc.html
# 我要如何与远程服务通信？（连接、认证、发送、接收）
# Python -> MSF RPC client（rpc.py） -> MSF RPC server -> MSF framework
# 2026-7-10 version 1.0.0

import requests
import msgpack

class MetasploitRPCClient:
    def __init__(self, host, port, username, password):
        # Configuration parameters
        self.host = host
        self.port = port
        self.username = username
        self.password = password

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
        if response.get("result") == "success":
            self.token = response.get("token")
        else:
            raise Exception("Failed to authenticate with Metasploit RPC server: " + str(response))
    
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
    
    def call(self, method: str, *params):
        """
        Send an authenticated RPC request.
        Injects the authentication token.
        """
        if self.token is None:
            self.login()
    
        return self._call(method, self.token, *params)

    def _call(self, method: str, *params):
        """
        Send a MessagePack RPC request to the Metasploit RPC server.
        examples: _post("auth.login", username, password)
        """
        if self.session is None:
            self.session = requests.Session()
        
        url = f'http://{self.host}:{self.port}/api'
        
        request_data = [method, *params]
        
        response = self.session.post(
            url, 
            data=msgpack.packb(request_data), 
            headers={'Content-Type': 'application/msgpack'},
            timeout=10,
            )
        
        response.raise_for_status()

        return msgpack.unpackb(response.content, raw=False)