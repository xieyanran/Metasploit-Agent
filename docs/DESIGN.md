# Metasploit Agent Design(version 1.0.0)

## Preparation

### Why Agent🧠?
- A workflow performs well when the decision logic can be made fully explicit — every branch reduces to an if/else condition, and the process can be represented as a static flowchart. Penetration testing rarely fits this model. Once a target's fingerprint has been identified, a single service may match several candidate exploit modules, and there is no fixed rule for ranking those candidates or deciding when to abandon a failing approach. Historically, this judgment has relied on the experience and intuition of the pentester rather than a codified procedure — precisely the kind of gap a flowchart cannot capture.

- An agent is a goal-oriented, autonomous system: it perceives its environment, and an LLM serves as its reasoning core — planning, reasoning over the current state, and invoking tools to pursue the pentest objective. Penetration testing already follows a fairly mature, well-established methodology; the opportunity here is not to reinvent that process, but to let an agent absorb and execute it. By automating the repetitive, low-judgment steps, the agent frees the human operator to focus on the critical decision points, extending the practical reach of the LLM and moving the discipline incrementally toward greater autonomy — improving overall efficiency while preserving the structure that already works.

### Task Environment (PEAS Model)
| Dimension    | Description |
|--------------|--------------------------------------------------------|
| Performance  | Successfully exploit the target within a given time budget, measured by session establishment rate, time-to-shell, and minimal false positives/negatives in module selection. |
| Environment  | The Metasploit Framework (via RPC/msfrpc API) and the target host(s)/network, including open ports, running services, and publicly available information (e.g., CVE databases, banners). |
| Actuators    | API calls that drive the attack chain: port scan → service/version fingerprinting → matching modules → configure module (set target/payload) → set exploit options → execute exploit (retry with alternate module on failure) → establish session → post-exploitation via Meterpreter. |
| Sensors      | JSON responses from the Metasploit RPC API (scan results, module output, session status) and publicly accessible target information (banners, HTTP headers, service metadata). |

### Paradigms Chosen

There are three popular, classic agent architectures in common use today: ReAct, Plan-and-Solve, and Reflection.

- **ReAct** follows a Thought → Action → Observation loop, producing a tight synergy between reasoning and acting — much like a detective working a case. This fits the exploitation phase well: a pentester observes the outcome of the previous step together with the current state of the target, then reasons about the next move. Reasoning keeps each action goal-directed, while each action's result supplies the evidence the next round of reasoning depends on.

- **Plan-and-Solve** also makes sense, but for a different phase. Reconnaissance is comparatively structured and produces a relatively static output — an asset inventory. In practice, this stage resembles a company's onboarding playbook for junior pentesters: a workflow-like checklist with fairly explicit boundaries. This makes it natural to decompose reconnaissance into sub-tasks that the agent can plan up front and then execute one by one.

- **Reflection** is left as future work. This architecture suits tasks that demand high precision and can absorb the added cost: it typically involves at least three LLM invocations, playing the roles of Executor, Reflector, and Refiner, iterating over multiple rounds to converge on a high-confidence result. Introducing a mechanism to evaluate and critique the agent's plans and actions would likely improve reliability, but the necessity of doing so — and the added API cost — still need to be weighed before adopting it.

### Current Design

The current design follows the industry-standard PTES methodology (Intelligence Gathering → Threat Modeling/Vulnerability Analysis → Exploitation → Post-Exploitation). The reconnaissance stage uses a Plan-and-Solve architecture to produce a detailed exploitation plan up front. Every subsequent stage uses a ReAct architecture, dynamically adjusting the original plan as new information emerges:

**Plan-and-Solve generates the initial penetration plan → ReAct executes it step by step, triggering a re-plan whenever a deviation or new discovery arises.**

This mirrors how a human pentester actually works — plan first, then adapt in the field.

### About the framework

This agent will rely on its own custom-built framework for the time being, rather than adopting an existing commercial one, for the following reasons:

- **Reduced cognitive overhead**. Mature commercial frameworks tend to wrap their functionality in heavy layers of abstraction and expose a large surface of configuration options. Understanding and correctly navigating that surface area imposes a real learning cost on developers.

- **Lower maintenance burden**. Commercial frameworks are typically updated and released frequently. Keeping pace with those changes — and absorbing the breaking changes that often come with them — adds ongoing maintenance overhead that a small, purpose-built codebase avoids.

- **Fewer dependency conflicts**. The extensive set of packages that mature frameworks pull in as dependencies can easily collide with the versions already required by the existing environment.

- **Tighter domain fit**. A custom framework can be tailored precisely to this project's vertical domain — penetration testing — allowing system prompts, safety/security constraints, and resource configurations to be designed specifically around that use case.

### Memory System Design 
- LLMs are stateless by design, so context-window limits can cause the model to lose early but important information, leave the agent unable to retain user preferences, limit its ability to learn from past successes and failures, and produce inconsistent answers across a multi-turn conversation. A memory system addresses these gaps.

- The need is even more acute for penetration testing: a real engagement can span hours or days across multiple target hosts and attack surfaces, so the agent must retain discovered assets, credentials, vulnerabilities, and previously tried payloads — otherwise **long-running tasks** lead to redundant scans, repeated trial-and-error, and even forgotten breakthroughs.

- Target environments also vary widely (defense posture, compliance boundaries, past successful exploit chains). Episodic/semantic memory is needed to accumulate **experience** — which techniques work in which environments — so the agent can make decisions tailored to a specific target in future engagements instead of reasoning from scratch every time.

### Retrieval-Augmented Generation Design
还在未来的拓展开发中

### Context Engineering
什么样的上下文配置，最有可能让模型产出我们期望的行为？
在推理阶段，如何策划与维护“最优的信息集合(tokens)”, 不仅仅包括提示本身，还包括其他会进入上下文窗口的一切信息。

- 为什么context Engineering 很重要
    - 上下文腐蚀(context rot): 随着上下文窗口中的tockens增加，模型从上下文中准确回忆信息的能力反而下降。因此，上下文被视作一种资源，并且具有边际收益递减。

- 目标：用尽可能少，但高信号密度的tockens,最大化获得期望结果的概率。

- Context Engineering组件
    - System Prompt 语言清晰、直白，信息层级把握在“刚刚好”的高度。常见两极误区：
        - 过度硬编码：在提示中写入复杂、脆弱的 if-else 逻辑，长期维护成本高、易碎。
        - 过于空泛：只给出宏观目标与泛化指引
        - 建议将提示分区组织（如 <background_information>、、工具指引、输出描述等），用 XML/Markdown 分隔。
    - Tools:
        - 工具定义了智能体与信息/行动空间的契约，必须促进效率：既要返回token 友好的信息，又要鼓励高效的智能体行为。
            - 职责单一、相互低重叠，接口语义清晰；
            - 对错误鲁棒
            - 入参描述明确、无歧义，充分发挥模型擅长的表达与推理能力
    - 示例（Few-shot）：始终推荐提供示例, 对 LLM 而言，好的示例胜过千言万语

- 面向长时程任务的上下文工程：
    - Compaction: 
        - 定义：当对话接近上下文上限时，对其进行高保真总结，并用该摘要重启一个新的上下文窗口，以维持长程连贯性。
        - 实践：让模型压缩并保留架构性决策、未解决缺陷、实现细节，丢弃重复的工具输出与噪声；新窗口携带压缩摘要 + 最近少量高相关工件（如“最近访问的若干文件”）。
        - 调参建议：先优化召回（确保不遗漏关键信息），再优化精确度（剔除冗余内容）；一种安全的“轻触式”压缩是对“深历史中的工具调用与结果”进行清理。
    - Structed note-taking:
        - 定义：也称“智能体记忆”。智能体以固定频率将关键信息写入上下文外的持久化存储，在后续阶段按需拉回。
        - 价值：以极低的上下文开销维持持久状态与依赖关系。例如维护 TODO 列表、项目 NOTES.md、关键结论/依赖/阻塞项的索引，跨数十次工具调用与多轮上下文重置仍能保持进度与一致性。
        - 说明：在非编码场景中同样有效（如长期策略性任务、游戏/仿真中的目标管理与统计计数）。结合第八章的 MemoryTool，可轻松实现文件式/向量式的外部记忆并在运行时检索。
    - Sub-agent architectures:
        - 

### Context Engineering && Memory System 

| 维度 | Context Engineering | Memory System |
|---|---|---|
| 关注层面 | 单次推理时，喂给模型的 token 集合该如何组织 | 信息在时间维度上该如何提取、分类、存储、检索、维护 |
| 核心问题 | "这一刻上下文窗口里该放什么" | "这些信息从哪来、该不该留、留多久、怎么被找回来" |
| 作用范围 | 运行时/单次 LLM 调用层面的策略 | 跨会话/跨 engagement 的系统架构层面设计 |
| 目标 | 用尽可能少、信号密度尽可能高的 token，最大化拿到期望输出的概率 | 让 agent 能持久保留资产/凭据/经验，避免长任务中重复扫描、重复试错 |
| 典型组件/技术 | System Prompt、Tools、Few-shot、Compaction、Structured note-taking | Working/Episodic/Semantic/Perceptual 四层记忆的提取时机、组织粒度、检索策略、遗忘与巩固机制 |
| 二者关系 | 约束 Memory 检索结果必须以什么形态、什么密度进入 context window（结论摘要+结构化标签，而非原始记录），否则会造成 context rot | 为 Context Engineering 提供可复用的长程知识供给层；Structured note-taking 本质就是"以固定频率写入外部持久化存储、按需拉回"的 memory 机制 |

一句话概括：Context Engineering 是通用的、面向单次推理的信息治理原则；Memory System 是在这个渗透测试场景下，把"哪些信息要跨会话留存"单独抽出来做的存储/检索/维护子系统——Memory 为 Context 提供长程知识，Context Engineering 反过来约束 Memory 输出的内容该以什么样子进入模型的推理窗口。

## MetaspolitAgents Architecture(version 1.0.0)
```
firstpentestAgent/
├── agent/                          # Agent实现层
│   ├── simple_agent.py              # SimpleAgent实现
│   ├── reconnaissance_planandsolve_agent.py  # Plan-and-Solve，驱动侦察阶段
│   ├── exploit_react_agent.py       # ReAct，驱动漏洞利用阶段
│   ├── MetaspolitSimpleAgent.py
│   ├── models.py                    # Agent数据模型
│   ├── state.py / state_manager.py  # Agent状态管理
│   └── planner/                     # 规划子模块
│       ├── planner.py
│       ├── strategy.py
│       ├── task_graph.py
│       └── workflow.py
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

## DeSign Memory System

### how to design the Memory System?
> 澄清场景，记忆分类，明确记忆的完整生命周期，反思与验证

- 强依赖场景：面向单用户还是多用户（涉及隔离和权限）？记忆需要跨会话还是只在单会话内？信息的更新频率如何，是偏静态的用户画像还是高频变化的任务状态？规模量级多大，是几百条还是千万级（决定要不要上向量库）？对准确性和延迟的要求哪个优先？
    - 面向单用户

    - **单用户 vs 多用户（隔离与权限）**：面向单用户场景，不涉及多租户之间的账号级权限隔离。但"单用户"不等于"无隔离需求"——同一操作者可能并行/串行执行多个 engagement（不同客户、不同 target），因此仍需要按 `engagement_id`/`target` 做逻辑边界，防止一次渗透中拿到的 credential、已知漏洞点串到另一个不相关的项目里，这是数据边界问题而非账号权限问题。

    - **单会话 vs 跨会话**：分记忆类型看待，不是统一答案。Working Memory 只在单 session 内有效（有 TTL/容量上限）；Episodic 和 Semantic Memory 必须跨会话持久化。原因是真实渗透往往跨越数小时到数天，中途会因为目标网络波动、RPC 超时、agent 进程重启等原因被迫拆分成多个 session——如果关键发现（资产、凭据、已验证的漏洞点）不能跨会话保留，就会在长任务里反复重复扫描、重复试错，甚至丢失刚拿到的突破口。

    - **更新频率（静态画像 vs 高频任务状态）**：以高频动态状态为主，静态部分占比小。Working/Episodic Memory 是渗透过程中的高频写入（每次扫描、每次 exploit 尝试都可能产生新记录）；Semantic Memory 更新频率低，是从大量 episodic 记录中周期性归纳出来的相对稳定的经验规则。本项目也没有典型 C 端场景下"用户兴趣画像"这类静态用户信息，取而代之的是客户 scope / Rules of Engagement 这类偏静态的约束条件——但这类信息是和 target/engagement 绑定的，而不是和"用户"本身绑定的，因此严格说不算传统意义上的用户画像。

    - **规模量级（决定是否上向量库）**：需要按记忆类型分层估算，而不是笼统给一个数量级。单次 engagement 产生的 Episodic Memory 量级大概率在几十到几百条（资产发现、凭据、exploit 尝试记录），即使长期跨多个 engagement 累积，大概率仍在万级以内，远达不到千万级；Semantic Memory 是归纳后的抽象规则，增长速度更慢，量级通常在百到千级。结论：当前阶段不需要为千万级规模设计独立的分布式向量数据库（如 Milvus/Pinecone），但 Episodic Memory 存在真实的语义检索需求（例如"这个 target 之前是否被扫描过类似的服务"这种非结构化匹配），因此仍值得引入轻量级、可嵌入的向量检索方案（如 SQLite + 本地向量索引，或 Chroma 这类嵌入式方案），而非重基础设施。

    - **准确性 vs 延迟**：准确性优先。渗透测试的核心特点是"单次记忆错误的代价很高"——如果检索时把一次失败的 exploit 误判为成功、或漏检了已经探明的凭据，轻则在长任务中重复动作浪费时间，重则触发目标 IDS/IPS 告警、打草惊蛇，甚至导致 engagement 被迫中止。这与强调实时响应的 C 端场景（客服对话、推荐系统）不同：pentest agent 每一步操作本身就有网络 RTT、exploit 执行时间（通常秒级到分钟级）作为基线开销，memory 检索多花的百毫秒到秒级延迟相对可忽略，但错误检索引发的连锁后果代价远高于这点延迟，因此设计上应优先保证召回与排序的准确性，而不是一味追求检索速度。

- Memory taxonomy and hierarchy: extraction, retrieval strategy, storage medium, and maintenance policy all differ by memory type:
| Memory Type | Description |
|---|---|
| Working Memory | Functions as short-term memory, holding the context of the current conversation. Its capacity is deliberately capped (e.g., 50 entries by default) to guarantee low-latency access, and its lifecycle is scoped to a single session. |
| Episodic Memory | Scoped to the current engagement. Records the attempts, actions, and outcomes generated over the course of a penetration test, and is used to reconstruct a roadmap of the full engagement lifecycle so the agent avoids repeating unproductive paths. |
| Semantic Memory | Designed to emulate the accumulated expertise of a senior pentester: abstract, generalized principles and reusable, transferable experience distilled from episodic records. |
| Perceptual Memory | Handles multimodal data such as images and audio and supports cross-modal retrieval, with its lifecycle managed dynamically. |

- 完整的生命周期: 提取/写入 -> 组织 -> 检索 -> 维护

- 记忆系统设计上的Trade-off/如何处理一些失败：记忆污染（错误信息被存下来后反复强化）、语义漂移（多轮摘要导致信息逐渐失真）、隐私问题（敏感信息该不该存、怎么删除、用户要求遗忘怎么办）。

### Memory Extraction
> 提取记忆的时机
> 如何判断哪些对话应该被提取储存为memory,该被储存为哪种类型的memory

- **The Timing**：提取时机的设计取舍，HelloAgents里是纯靠模型自主判断。

    - **业界参考**：主流开源pentest agent项目实际用的时机类型选择是非常收敛的。
        - **PentAGI**：working context / episodic history / long-term vector store三层，用"chain summarization"在上下文快超限时自动压缩较早历史——即**容量/窗口触发**
        - **VulnBot**（Planner/Memory Retriever/Generator/Executor/Summarizer五模块）：Summarizer只在PTES阶段切换（侦察→扫描→利用）时工作，摘要关键结论并传递给下一阶段——即**阶段转换触发**，且只做结论摘要，不逐轮处理
        - **mem0**（当前最主流的通用记忆层，被大量agent项目直接复用）：本质是逐轮提取，但提取过程**异步执行、不阻塞主循环**（`add()`在每轮后调用，LLM抽取/去重/写库在后台跑），且采用**ADD-only**策略（只增不改/不删），避免过早合并导致信息丢失。这是解决"逐轮提取成本太高"问题的关键手段——不是不逐轮，而是把它挪到异步

    - **方案**：
        1. Working memory：自动直写入内存，不经过LLM
        2. Episodic memory：每轮对话后触发，提交给LLM，做是否是Episodic Memory的判断。ADD-only，不覆盖旧记录——一次失败的exploit尝试和后续成功的尝试都应保留，便于复盘攻击路径的因果链。更经济的做法是，单独训练一个较小的模型用于此处，一开始是想做Event-triggered timing,并且利用正则表达式判断每个事件，但其分类准确性过于僵硬。
        3. Semantic memory：PTES阶段边界触发，对该阶段积累的episodic memory做一次归纳提炼；兜底在engagement结束时再做一次归纳提炼，不需要额外的重要性打分机制（阶段边界本身就是低成本、天然存在的触发点）。参考主流开源项目VulnBot。
        4. Perceptual memory维持"证据到达即处理"不变

- **记忆类型的储存判断**：涉及memory/manager.py/中def _classify_memory_type的设计

    - Working Memory判断: 默认进入,仅在当前的session中有效，并且在session内部还有TTL/容量边界
    
    - Episodic Memory判断：跨session进行记忆，绑定具体的target/session的一次性事件，edg. 
        - New assests: 发现主机/端口/服务/版本
        - New Credentials or 密钥 
        - 利用尝试及其结果（需区分失败原因：技术性失败[漏洞不存在/已修复] vs 操作性失败[网络不通/payload编码错误/RPC超时]，避免把操作性失败误判为"该手法对此环境无效"）
        - 侦察阶段的阴性结果：端口关闭、服务未匹配任何已知exploit等，避免下次对同一target重复扫描
        - Target防御措施的发现
        - 权限提升/横向移动相关的关键节点，及跨资产的因果链条（例如"凭据X取自主机A，被用于登录主机B"，记录攻击路径的依赖关系而非孤立事件）
        - OSINT/被动情报：子域名、泄露的代码仓库、社工线索等绑定该target的一次性发现
        - Scope,客户的限制条件（与target强绑定，因此归入Episodic；与target无关、可跨engagement复用的规则/技巧归入Semantic）
    
    - Semantic Memory判断：跨session进行记忆，脱离具体的target，更抽象可复用的知识，概念以及规则
        - 判断标准："换一个目标还有用吗"——内容脱离具体target/session后依然成立，且能拆解为实体+关系（如 CVE↔受影响服务版本、exploit模块↔前置条件、技术↔检测/防御手段），才适合归入Semantic
        - 漏洞/CVE的技术特征与触发条件
        - exploit模块的适用边界与失效条件（例如架构要求、在何种防御配置下经常失败）——这类规律通常是从多条episodic失败记录中归纳出来的，而不是单次尝试的直接结论
        - 漏洞的分析与判定的技巧
        - 权限提升/横向移动的通用策略
        - 工具使用的最佳实践与已知坑
        - 防御规避（EDR/AV/WAF）的通用技巧
        - 来源不止是单轮对话内容的直接判断，也包括对多条episodic记忆的归纳提炼（对应代码里的`find_patterns`/`consolidate_memories`）
    
    - Perceptual Memory判断： 截图/流量包/音频等非文本证据，来自其他外部未集成的工具

### Memory Organize
- 粒度：一条记忆，一个MemoryItem
    - memory id
    - memory type
    - user id（单用户场景下不适用，作为以后多用户 agent 的扩展字段保留）
    - timestamp
    - importance
    - content
    - metadata

- MetaData Schema:
    > 设计原则：metadata 只放"用于过滤/检索/生命周期判断"的结构化 key，参考 VulnBot 的 Summarizer 只产出"结论摘要 + 少量结构化标签"而不是原始工具输出，PentAGI 的三层 context 也只在层间传递压缩后的摘要。
    > 分层设计：通用层（四类记忆共享）+ 类型特有层（仅 episodic/semantic/perceptual 各自需要）。

    - **通用层**（working/episodic/semantic/perceptual 共用）：
        - `session_id` (str, working/episodic/perceptual 必填/仅 semantic 可选)：归属会话，已在 `memory_tool.py` 实现自动写入。semantic 的检索边界本身是全局的（跨 session/engagement/target，见 Semantic Memory 检索策略一节），从不按 session_id 过滤，留空不影响任何功能。
        - `engagement_id` (str, episodic 必填/working、perceptual 建议填/仅 semantic 可选)：项目级作用域标识，比现有的 `target_ref` 高一层——一次 engagement 可能涉及多个 target，拆成两个字段能同时支持"查这个项目下所有记录"和"查这台主机下所有记录"两种检索粒度，呼应"单用户但需要 engagement 级隔离"的结论。semantic 同上不需要——provenance 已由 `derived_from` 追溯回具体 episodic 记录，不需要在 semantic 记录自身冗余存一份。
        - `target_ref` (str, episodic 建议填/perceptual 建议填)：资产级标识（IP/host），沿用已有字段。perceptual 建议填的原因见 Perceptual Memory 检索策略一节——"和当前排查的 target/session 是否对应"是证据类记忆的重要过滤维度。
        - `phase` (enum: `recon`/`vuln_analysis`/`exploitation`/`post_exploitation`)：对齐 PTES 四阶段，复用 VulnBot 阶段转换触发 Summarizer 的做法——既是提取时机的触发条件，也是检索时的过滤维度（例如做利用阶段推理时，只想召回该 target 在侦察阶段发现的资产，不想被后渗透阶段的记录干扰）
        - `is_target_bound` (bool)：episodic/semantic 分类开关，已有，保留
        - `updated_at` (int, 时间戳)：存储层（SQLite `memories.updated_at`）本就在每次 `update()` 时自动维护，直接透出到 metadata 不增加成本；用于区分"写入后再没动过"与"被反复修正/强化"的记录，也可作为 semantic 知识 `confidence` 走向稳定的辅助信号，以及时间衰减类遗忘策略的更优时间基准（用最后修正时间而非最初创建时间，避免误删近期被强化过的老记录）
        - `last_accessed_at` (int, 时间戳，检索命中时更新)：反映"是否还在被实际使用"，与 importance/created_at 是完全不同的信号，补上现有 `forget_memories` 缺失的第四种策略——访问频率遗忘（LRU 式）：重要性一般但持续被召回的记录不该被淘汰，反之从未被再次检索过的记录是更安全的遗忘候选。写入成本可控：episodic/semantic 的 `retrieve()` 本就要 `doc_store.get_memory()` 读一次 SQLite，顺带一次 `UPDATE` 不是新增往返；working memory 是内存 list，原地改字段基本零成本

    - **Episodic 特有**：
        - `event_type` (enum，已有 8 个取值：asset_discovery/credential_found/exploit_attempt/recon_negative/defense_observed/privesc_lateral_move/osint_finding/scope_directive)
        - `outcome` (enum: `success`/`tech_fail`/`op_fail`/`negative`)：建议把现有的自由字符串 `outcome` 收紧成固定枚举，直接落实 DESIGN.md 反复强调的"技术性失败 vs 操作性失败"区分，避免把一次 RPC 超时误判为"该手法对此环境无效"
        - `causal_ref` (list[str]，指向其他 episodic memory_id)：记录攻击路径的依赖关系（如"凭据 X 取自主机 A，被用于登录主机 B"），替代现有代码里基本没被用到的 `participants`/`context`/`tags`

    - **Semantic 特有**：
        - `entities` (list[str])：已有，喂给 Neo4j 知识图谱
        - `confidence` (float 0-1)：与 `importance` 解耦——`importance` 回答"这条知识有多重要"，`confidence` 回答"这条知识有多可信"。只从 1 条 episodic 样本归纳出的规则和从 10 次重复失败归纳出的规则，重要性可能都高，但可信度不同，这是 mem0/Generative Agents 类系统的常见做法
        - `derived_from` (list[str]，指向被归纳的 episodic memory_id)：追溯这条 semantic 知识由哪些 episodic 记录 consolidate 而来，用一个溯源字段替代真正的版本快照，兼顾可审计性和实现成本

    - **Perceptual 特有**：
        - `modality` / `raw_data`：已有，保留

- 更新语义: 不同记忆种类有不同的更新策略，包含在Memory Maintence设计中
    - Working Memory 采用覆盖式更新语义
    - Episodic Memory 采用Add-Only策略，可审计，回溯
    - Semantic Memory 不简单局限于单一的覆盖式，追加式更新策略，在Maintence中有详细的描述

- 记忆分层: 将记忆按照之前的分类，分成不同的存储区，每个区独立配置检索，维护等策略。

### Memory Retrievel
> 检索策略不是独立设计的，而是由"记忆分类与层次"一节里已经确定的特征反推出来的。

- **Working Memory 检索策略thinking && design**
    - 规模量级: 几十条，本质上小窗口排序问题，不必引入向量数据库
    - 检索边界: 同一个session_id内，和当前这一步最相关的近期上下文是什么
    - 排序分数：时间近因应该是主导因子,加入importance weight和关键词命中。

- **Episodic Memory 检索策略的thinking && design**
    - 不引入向量数据库也不做语义召回: episodic 内容里最关键的部分（CVE 编号、版本号、host 名）向量相似度并不能进行精准衡量, LLM直接读原文更精准。
    - **检索边界**：`engagement_id` 是唯一边界。跨 engagement 的"有没有见过类似情况"这类模糊参考需求，完全交给 Semantic Memory 检索——这是已有分类标准（"换个目标还有用吗"）的自然延伸：episodic 只回答"这个 engagement 里发生过什么"。
   - 检索思路: LLM先查询Semantic（联想相似情境/经验，思考可能的攻击链），引入RAG系统之后也可以作为reference→ 基于此LLM再判断具体metadata参数作SQL查询。
    
- **Semantic Memory 检索策略的thinking && design**
    - **检索边界**：没有任何硬性的过滤边界，跨 session/engagement/target 全局检索——这是已有分类标准（"换个目标还有用吗"）的自然延伸，semantic memory 本身就是脱离具体 target 才成立的经验。

    - **实体抽取**：正则 + 词典为主，不依赖通用 NER 作为主匹配信号。
        - 正则抓格式规整的结构化标识符：CVE 编号（`CVE-\d{4}-\d{4,7}`）、MS 漏洞编号（`MS\d{2}-\d{3}`）、msf 模块路径、端口号等。
        - 词典抓常见服务/组件/协议/防御产品名（SMB、Redis、Struts2、WAF 厂商名等），这份词典随经验积累持续增长——在 episodic→semantic 归纳环节顺手把新出现的服务/组件名补充进去，不需要重新训练模型。
        - 通用 NER（spaCy）继续并行跑，补充人名/组织/地域类辅助实体、写入图谱做辅助节点，但不作为图检索的主匹配信号——它对 CVE 编号、msf 模块路径这类领域技术词基本不会识别为实体，靠它做主信号图检索这条腿等于半失效。
        - Query 和 memory content 用同一套抽取逻辑，保证两边的实体 id 能对上。

    - **双路召回**：向量检索（Qdrant 相似度）+ 图检索（Neo4j，用抽出的实体找 2 跳内相关记忆），两路各自独立召回后再融合，不互相替代。

    - **融合排序公式**：
        ```
        base_relevance    = vector_score * 0.7 + graph_score * 0.3
        importance_weight  = 0.8 + importance * 0.4         区间 [0.8, 1.2]
        confidence_weight  = 0.7 + confidence * 0.6          区间 [0.7, 1.3]
        combined_score     = base_relevance * importance_weight * confidence_weight
        ```
        - `confidence_weight` 新增，且区间比 `importance_weight` 更宽——可信度应该比重要性更能决定排序优先级：一条不可信的经验即使重要性判断很高也不该排到前面，这是把 `confidence`/`disputed` 这两个已经设计在 metadata schema 里、但之前没有真正参与排序的字段接回检索链路。
        - 0.7/0.3 的向量/图权重先沿用已有比例，后续如果有真实检索日志支持再调整。

    - **Disputed 过滤规则**：候选集合里若某条 disputed 记忆存在未被标记的替代项（`disputed_with` 指向的记忆也在候选集中），直接剔除该 disputed 记忆，不进入返回结果；若 disputed 记忆是唯一候选（没有替代项一起出现），保留但在返回的 `MemoryItem.metadata` 里显式标注 `disputed=True`，把风险信号交给上层 LLM 自行判断是否采信，而不是静默隐藏——错误的经验比没有经验更危险，这一步直接对应"记忆污染"那一节提到的风险。

    - **失败兜底**：图检索异常/超时不能阻塞向量检索的返回，两路独立 fail-open，保证最差情况下退化为"纯向量检索"，而不是整个 retrieve() 抛异常返回空。

    - 检索前的 query 联想扩展（让 LLM 先把 query 联想成候选关键词再检索）评估过但暂不引入，复杂度和当前阶段的收益不匹配，先把上面几项落地、有实际检索数据后再重新评估。

- **Perceptual Memory 检索策略的思路**
    - 原始内容（截图、流量包、音频）本身没有可供关键词或结构化字段直接匹配的文本语义，检索天然只能走相似度这一条路——这是数据形态决定的，不是设计取舍的结果。
    - 理想情况下应支持跨模态检索（用文字描述找截图），但这依赖专门的跨模态编码器（如 CLIP/CLAP）；在没有引入这类模型之前，检索范围只能收窄到同模态内比较，这是当前能力边界带来的临时取舍，不是长期设计目标——一旦跨模态编码可用，检索思路应自然扩展到跨模态查询，不需要重新设计这一层。
    - 这类记忆是"证据"而非"结论"，排序上除了语义相似度，还要看召回的证据是否仍然新鲜、和当前排查的 target/session 是否对应——时间和归属关系是重要的辅助过滤维度，不能只靠相似度分数。

- 量化指标:
    - Precision@k / Recall@k：在返回的前 k 条里算准确率和召回率，最基础。
    - 


### Memory Maintence
- **Memory Forgetting/Eviction**: a unified forgetting mechanism
    - Four forgetting strategies: importance-based, time-based, capacity-based, and access-based.
    - Working Memory is the only type with "automatic" triggering: every write triggers both the time-based and capacity-based forgetting strategies.
    - Episodic Memory is tightly scoped to the engagement, supporting causal-chain reasoning for lateral-movement/privilege-escalation scenarios (spanning multiple targets within the same engagement). Accordingly, this memory type carries an `engagement_id` retrieval boundary.
        - Resolved (see "Memory Retrievel" → Episodic): `engagement_id` is now the sole boundary, and retrieval is LLM-driven structured lookup (target_ref/phase/causal_ref) rather than vector similarity — cross-engagement contamination can no longer sneak in through an embedding match, since there is no embedding match in this path anymore.
        - This memory type does not need to concern itself much with deduplication, consistency, or refinement. Its lifecycle is tightly bound to the engagement, and event-triggered filtering is already applied at write time (only a handful of qualifying events are ever converted into a record), so the resulting volume never grows large enough to justify spending LLM resources on maintenance. Keeping a clean, explicit record of every action — success or failure alike — is itself the point, and mirrors how real-world penetration testers actually work.
- **Semantic Memory Maintenance**: Semantic memories are currently generated by summarizing episodic memories — this is where consistency, deduplication, and refinement matter most. The design intent is to emulate the experience-accumulation process of a senior pentester, giving the agent a basis for continuous self-improvement. This is harder to design than the other memory types, and no solution currently seems capable of achieving that goal with full reliability. Periodic LLM-driven passes are needed to refine entries, detect contradictions, enforce consistency, and deduplicate records.
    - Deduplication is applied to each newly generated semantic memory individually: a vector-similarity comparison first does a coarse pass to assemble a candidate set, which is then dedup-checked and adjudicated by an LLM.
    - Contradiction detection and consistency maintenance: candidate generation is graph-based, built on the Neo4j entity graph — other memories that share at least one entity with the newly added entry form the candidate set for contradiction detection, which is then adjudicated by an LLM.
        - We define four possible relations between a pair of semantic memories, adjudicated by the LLM:
        - duplicate: the two statements are essentially about the same thing; deduplicate them.
        - contradiction: under the same premise/event (referring to the episodic event that originally triggered the memory), the two statements reach mutually exclusive conclusions; this requires contradiction-resolution handling, and falls back to human review whenever it cannot be adjudicated automatically.
        - complementary: the two statements are related but not in conflict — each is independently valid and complements the other, so both are worth keeping.
        - unrelated: the two statements are merely topically related; their actual content has no real relationship.
    - Refinement: no design for this yet.
- **Memory Consolidation**: Essentially limited to consolidating episodic memory into semantic memory — summarizing a batch of episodic records from a given stage into semantic memory. By analogy with the forgetting strategies, an importance-based or access-based consolidation strategy could be designed, but the idea remains somewhat underspecified, so implementation is not yet planned.

## How to deal with the problem?
记忆污染的风险可能比笔记里写的更值得重视。即使在同一个 engagement_id 边界内，也仍然可能出现跨目标串扰（cross-target bleed）——比如 Target A 上有效的凭据或成功的攻击手法，仅仅因为共享同一个 engagement scope，就被检索出来并错误地套用到 Target B 上；也可能出现信息过期（staleness）的情况——某个漏洞在 engagement 早期被记录为"可利用"，但期间目标可能已打补丁，或 IDS 规则被收紧，而这条过时记录却仍会被当作有效信息反复检索出来。

还有一个更贴合渗透测试场景、值得明确指出的污染途径：由于 episodic memory 是从工具/目标的返回数据中写入的，而目标环境本身是对抗性的，防御方或蜜罐完全可能故意提供误导性的服务 banner、伪造的凭据，或精心构造的响应，这些内容一旦被当作"事实"存下来，就会污染后续的推理——这更接近于"通过工具输出实施的 prompt injection"问题，而不是普通的记忆漂移。建议补充一点：检索/写入时应该以 target_id 为边界进行限定，而不仅仅是 engagement_id；同时，源自未经验证的目标响应的数据，其初始 confidence 应该低于 agent 自行验证过的结果。

关于confidence以及importance

## ContextBuilder Design

### Design Motivation and Goal

- 统一入口：将"获取(Gather)- 选择(Select)- 结构化(Structure)- 压缩(Compress)"抽象为可复用流水线。

- 稳定形态：输出固定骨架的上下文模板，便于调试、A/B 测试与评估。我们采用了分区组织的模板结构：
    - [Role & Policies]：明确 Agent 的角色定位和行为准则
    - [Task]：当前需要完成的具体任务
    - [State]：Agent 的当前状态和上下文信息
    - [Evidence]：从外部知识库检索的证据信息
    - [Context]：历史对话和相关记忆
    - [Output]：期望的输出格式和要求

- 预算守护：在 token 预算内尽量保留高价值信息，对超限上下文提供兜底压缩策略。这确保了即使在信息量巨大的场景下，系统也能稳定运行。

- 最小规则：不引入来源/优先级等分类维度，避免复杂度增长。实践表明，基于相关性和新近性的简单评分机制，在大多数场景下已经足够有效。
    
### 核心数据结构

### GSSC 流水线详解

- Gather: 多源信息汇集
    - P0: 系统指令
    - P1: 从记忆中获取任务状态与关键结论
        - 执行顺序：semantic 先行，episodic 依赖 semantic 的检索结果做参数判断
        - semantic memory：直接用 user_query 做语义检索，检索结果同时作为下一步 episodic 参数判断的输入
        - episodic memory：engagement_id 是唯一安全边界，必带且不受判断结果影响——缺失则跳过整个分支，不做无边界搜索；target_ref/phase/event_type/query 这几个收窄条件不再由代码直接从当前 state 取值，而是交给 LLM 基于 semantic 的检索结果判断，判断结果也可以是 should_query=false（本轮不查）。LLM 不可用、调用异常或输出解析失败时，兜底退回到用当前 state 的 target_ref/phase（不设 event_type），即和旧方案一致的行为，不会比没有这一步更差
        - working memory：本 session 内最近几次工具调用的 Action+Observation；limit 刻意设小（当前 3 条）
    - P2: 从RAG系统检索相关知识
    - P3: 添加对话历史
    - P4: 添加自定义context packet

- Select：智能信息选择（直接决定上下文的质量）
    - 排序依据：复合分 = 0.7×相关性 + 0.3×新近性
        - 相关性：user_query 与候选包内容的关键词重叠比例——纯词面匹配，不引入向量检索，候选包量级小（个位数到十几个），没必要为此上向量库
        - 新近性：指数衰减 `exp(-Δt/3600)`，1小时时间尺度，越新的信息权重越高，但不会断崖式清零
    - 优先级白名单：`{instructions, task_state, recent_actions}` 固定纳入，不受最小相关性阈值（`min_relevance=0.3`）过滤
        - 原因：这几类内容本质是系统指令/结构化事件记录/原始工具日志，和自然语言 user_query 天然缺乏字面重叠，若和其余内容一样走关键词相关性过滤，几乎总会被误判为"不相关"而丢弃——等于让 P0/P1 辛苦查回来的东西形同虚设。相关性过滤只对 related_memory（semantic）/knowledge_base/history 这类"和当前问题强相关才值得保留"的内容生效
    - 预算填充：贪心策略。先放入优先包（不排序，全部尝试塞入），再按复合分从高到低加入其余包，一旦下一个包会超出可用预算（`max_tokens` 扣除生成余量后的可用值）就跳过——不做整体重排或部分裁剪，保证每个被选中的包内容完整

- Structure：结构化输出
    - 固定六段模板，按 `metadata["type"]` 路由，某类型没有命中的包时该分区整体不出现（不留空标题占位）：
        - `[Role & Policies]` ← instructions（P0）
        - `[Task]` ← user_query 原样嵌入，不经过 Select 筛选，每次必然出现
        - `[State]` ← task_state（episodic 关键结论）+ recent_actions（working 最近动作），两个来源在同一分区内用不同子标题区分，让 LLM 能分辨"这是复盘出的结论"还是"这是刚做过的动作"
        - `[Evidence]` ← related_memory（semantic）/knowledge_base（RAG，当前禁用）/retrieval/tool_result 等"证据类"内容统一归入
        - `[Context]` ← 对话历史
        - `[Output]` ← 固定的输出格式约束（结论/依据/风险与假设/下一步行动建议），不依赖检索结果，每次都追加在最后
    - 设计取舍：分区边界按"内容语义角色"划分，不是按"来源模块"划分——例如 episodic 和 working 是两个不同的记忆子系统，但因为都回答"目前进展到哪"，被合并进同一个 `[State]` 分区；这样 LLM 消费到的上下文骨架是稳定的，不会随内部实现调整（比如以后给 P1 加第四种记忆来源）而变化

- Compress：兜底压缩（对上下文进行压缩处理）
    - 触发条件：仅当结构化文本的 token 数超过可用预算时才动作，未超预算直接原样返回，不做任何无谓处理
    - 当前策略：按行贪心截断——逐行累加 token 数，一旦下一行会超预算就整体停止，保留已经拼接的完整行（不做行内截断），尽量维持已保留分区的结构完整性，而不是不看结构地砍到定长
    - 已知局限：这是"硬截断"而非"高保真摘要"，超出预算的内容是被整体丢弃而不是压缩保留要点——上面 Context Engineering 一节里 Compaction 提到的"让模型压缩并保留架构性决策"式的智能摘要目前还没有用在这里，只是先用简单兜底策略保证不超预算；后续如果发现频繁触发 Compress，值得替换成真正的 LLM 摘要压缩



