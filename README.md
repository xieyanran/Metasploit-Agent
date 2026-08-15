# Metaspolit Agent

## 

### Preparations
- Install Metasploit elegant: https://docs.metasploit.com/docs/using-metasploit/getting-started/nightly-installers.html

- Start RPC Server
    - Note: 每次重新打开 Metasploit，都需要重新执行, 因为这是一个插件，不会默认一直开启。

    ```
    load msgrpc ServerHost=127.0.0.1 ServerPort=Portnum User=username Pass=password SSL=false
    ```

## MetaspolitAgent Architecture

```
firstpentestAgent/
├── agent/                          # Agent实现层
│   ├── simple_agent.py              # SimpleAgent实现
│   ├── reconnaissance_planandsolve_agent.py  # Plan-and-Solve，驱动侦察阶段
│   ├── post_recon_react_agent.py    # ReAct，驱动Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation三阶段
│   ├── MetaspolitSimpleAgent.py
│   ├── models.py                    # Agent数据模型
│   └── state.py                     # Agent状态管理
│
├── core/                           # 核心框架层
│   ├── agent.py                     # Agent基类
│   ├── llm.py / my_llm.py           # LLM统一接口
│   ├── llm_response.py
│   ├── message.py                   # 消息系统
│   ├── config.py                    # 配置管理
│   ├── lifecycle.py                 # 生命周期管理
│   ├── streaming.py
│   └── exceptions.py                # 异常体系
│
├── context/                        # Context Engineering层
│   └── builder.py                   # ContextBuilder: Gather-Select-Structure-Compress
│
├── memory/                         # 记忆系统层
│   ├── manager.py                   # 记忆管理入口
│   ├── base.py
│   ├── extraction.py                # 记忆提取
│   ├── maintenance.py               # 记忆维护（遗忘/去重/巩固）
│   ├── embedding.py
│   ├── types/                       # 四类记忆
│   │   ├── working.py
│   │   ├── episodic.py
│   │   ├── semantic.py
│   │   └── perceptual.py
│   ├── storage/                     # 存储介质
│   │   ├── document_store.py        # SQLite
│   │   ├── qdrant_store.py          # 向量库
│   │   └── neo4j_store.py           # 图数据库
│   └── rag/                         # RAG（规划中，暂未启用）
│       ├── document.py
│       └── pipeline.py
│
├── metasploit/                     # Metasploit RPC封装层
│   ├── client.py / rpc.py           # msfrpc客户端
│   ├── core.py / console.py
│   ├── modules.py / plugins.py
│   ├── job.py / session.py
│   └── exceptions.py
│
├── tools/                          # 工具系统层
│   ├── base.py                      # 工具基类
│   ├── registry.py                  # 工具注册机制
│   ├── chain.py                     # 工具链管理系统
│   ├── async_execute.py             # 异步工具执行器
│   ├── response.py
│   └── builtin/                     # 内置工具集
│       ├── nmap_scan.py
│       ├── search_module.py / get_module_info.py
│       ├── run_module.py / set_option.py / show_option.py
│       ├── list_jobs.py / job_info.py / stop_job.py
│       ├── list_sessions.py / execute_session.py / stop_session.py / kill_meterpreter_session.py
│       ├── session_compatible_modules.py / compatible_payloads.py
│       ├── shell_upgrade.py
│       ├── memory_tool.py
│       └── rag_tool.py
│
├── docs/                           # 设计文档
├── tests/                          # 测试
└── examples/
```

> 更详细的设计动机与权衡见 [`docs/DESIGN.md`](docs/DESIGN.md)。
