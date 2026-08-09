# Metaspolit Agent

## 

### Preparations
- Install Metasploit elegant: https://docs.metasploit.com/docs/using-metasploit/getting-started/nightly-installers.html

- Start RPC Server
    - Note: 每次重新打开 Metasploit，都需要重新执行, 因为这是一个插件，不会默认一直开启。

    ```
    load msgrpc ServerHost=127.0.0.1 ServerPort=Portnum User=username Pass=password SSL=false
    ```
