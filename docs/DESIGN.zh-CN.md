# Metasploit Agent 设计文档（版本 1.0.0）

[English](DESIGN.md) | 简体中文

## 准备工作

### 为什么用 Agent🧠？
- 当决策逻辑能够被完全显式化——每一个分支都能归约成一个 if/else 条件，整个流程能被画成一张静态流程图时，workflow（工作流）的表现会很好。渗透测试很少符合这种模型。一旦目标的指纹被识别出来，单个服务往往会匹配到多个候选利用模块，而对这些候选项该如何排序、该在什么时候放弃一条正在失败的路径，都没有固定规则可循。历史上，这类判断一直依赖渗透测试人员的经验和直觉，而不是某种编码好的流程——这正是流程图无法捕捉的那部分。

- Agent 是一个目标导向、自主运行的系统：它感知所处环境，并以 LLM 作为其推理核心——规划、对当前状态进行推理、调用工具来推进渗透测试目标。渗透测试本身已经有一套相当成熟、公认的方法论；这里的机会不在于重新发明这套流程，而在于让 agent 去吸收并执行它。通过把重复性的、低判断含量的步骤自动化，agent 让人类操作者得以专注在关键决策点上，从而扩展 LLM 的实际能力边界，让这个学科逐步走向更高的自主化程度——在保留已经行之有效的结构的同时提升整体效率。

### 任务环境（PEAS 模型）
| 维度 | 描述 |
|--------------|--------------------------------------------------------|
| Performance（性能） | 在给定时间预算内成功利用目标，用会话建立率、拿到 shell 的耗时，以及模块选择中的误报/漏报最小化来衡量。 |
| Environment（环境） | Metasploit Framework（通过 RPC/msfrpc API）以及目标主机/网络，包括开放端口、正在运行的服务，以及公开可获取的信息（如 CVE 数据库、banner）。 |
| Actuators（执行器） | 驱动攻击链的一系列 API 调用：端口扫描 → 服务/版本指纹识别 → 匹配模块 → 配置模块（设置目标/payload）→ 设置利用选项 → 执行利用（失败则换一个模块重试）→ 建立会话 → 通过 Meterpreter 进行后渗透。 |
| Sensors（传感器） | 来自 Metasploit RPC API 的 JSON 响应（扫描结果、模块输出、会话状态），以及公开可获取的目标信息（banner、HTTP 头、服务元数据）。 |

### 范式选择

当前业界常用的经典 agent 架构主要有三种：ReAct、Plan-and-Solve、Reflection。

- **ReAct** 遵循 Thought → Action → Observation 循环，在推理与行动之间形成紧密的协同——很像侦探破案的方式。这很适合利用阶段：渗透测试人员会结合上一步的结果和目标当前的状态来观察，然后推理出下一步该做什么。推理让每一次行动都保持目标导向，而每一次行动的结果又为下一轮推理提供了依据。

- **Plan-and-Solve** 同样合理，但适用于不同的阶段。侦察阶段相对结构化，产出的结果也相对静态——一份资产清单。实践中，这个阶段很像一家公司给初级渗透测试人员准备的入职操作手册：一份边界比较明确的、类似 workflow 的检查清单。这使得把侦察阶段拆解为若干子任务、让 agent 提前规划好再逐一执行变得很自然。

- **Reflection** 留作未来的工作。这种架构适合那些对精度要求很高、并且能承担额外成本的任务：通常至少需要三次 LLM 调用，分别扮演 Executor、Reflector、Refiner 的角色，经过多轮迭代收敛出一个高置信度的结果。引入一种机制来评估和批判 agent 的计划与行动，大概率能提升可靠性，但这么做的必要性——以及随之增加的 API 成本——在采用之前仍需要权衡。

### 当前设计

当前设计遵循业界标准的 PTES 方法论（情报收集 → 威胁建模/漏洞分析 → 利用 → 后渗透）。侦察阶段采用 Plan-and-Solve 架构（`agent/reconnaissance_planandsolve_agent.py::PlanSolveAgent`）提前生成一份详细的利用计划。此后的每个阶段都采用 ReAct 架构，随着新信息的出现动态调整原有计划——具体做法是：同一个 `agent/post_recon_react_agent.py::PostReconReActAgent` 实例被复用于三个阶段（漏洞分析、利用、后渗透）：编排器在每个阶段边界调用一次 `set_ptes_phase()`，再重新调用 `run()`，agent 每次都会根据 `state.ptes_phase` 现算出该阶段专属的 system prompt（见下文「ReAct 阶段 × Context/Memory 融合设计」）。agent 永远不会自己决定某个阶段何时结束——这个权力始终留在编排器手里：

**Plan-and-Solve 生成初始渗透计划 → ReAct 逐步执行该计划，一旦出现偏差或新发现就触发重新规划。**

这正是真实渗透测试人员的工作方式——先制定计划，再在实战中随机应变。

### 关于框架选择

这个 agent 目前会依赖一套自己搭建的框架，而不是采用某个现成的商业框架，原因如下：

- **降低认知负担**。成熟的商业框架往往会把功能包裹在厚重的抽象层里，暴露出一大堆配置项。理解并正确使用这些配置项，对开发者而言是一笔实实在在的学习成本。

- **降低维护负担**。商业框架通常更新和发版都很频繁。跟上这些变化——并消化随之而来的破坏性变更——会带来持续的维护开销，而一个小型、专门定制的代码库可以避免这一点。

- **减少依赖冲突**。成熟框架为了实现功能会引入大量依赖包，这很容易和现有环境里已经要求的版本产生冲突。

- **更贴合领域需求**。自建框架可以针对本项目的垂直领域——渗透测试——做精确定制，让 system prompt、安全/合规约束、资源配置都能专门围绕这个场景来设计。

### 记忆系统设计
- LLM 天生是无状态的，因此上下文窗口的限制会导致模型丢失早期但重要的信息，让 agent 无法保留用户偏好，限制其从过去的成败中学习的能力，并在多轮对话中产生前后不一致的回答。记忆系统正是用来弥补这些缺口的。

- 对渗透测试来说，这种需求更加迫切：一次真实的 engagement 可能横跨数小时到数天、涉及多个目标主机和攻击面，因此 agent 必须保留已发现的资产、凭据、漏洞，以及此前尝试过的 payload——否则**长程任务**会导致重复扫描、重复试错，甚至遗忘已经取得的突破。

- 目标环境本身也千差万别（防御态势、合规边界、过往成功的利用链路）。需要情景记忆/语义记忆来积累**经验**——哪些技术在哪些环境下有效——这样 agent 才能在未来的 engagement 中针对具体目标做出定制化决策，而不是每次都从零开始推理。

### 检索增强生成（RAG）设计
还在未来的拓展开发中

### 上下文工程
什么样的上下文配置，最有可能让模型产出我们期望的行为？
在推理阶段，如何策划与维护"最优的信息集合(tokens)", 不仅仅包括提示本身，还包括其他会进入上下文窗口的一切信息。

- 为什么context Engineering 很重要
    - 上下文腐蚀(context rot): 随着上下文窗口中的tockens增加，模型从上下文中准确回忆信息的能力反而下降。因此，上下文被视作一种资源，并且具有边际收益递减。

- 目标：用尽可能少，但高信号密度的tockens,最大化获得期望结果的概率。

- Context Engineering组件
    - System Prompt 语言清晰、直白，信息层级把握在"刚刚好"的高度。常见两极误区：
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
        - 实践：让模型压缩并保留架构性决策、未解决缺陷、实现细节，丢弃重复的工具输出与噪声；新窗口携带压缩摘要 + 最近少量高相关工件（如"最近访问的若干文件"）。
        - 调参建议：先优化召回（确保不遗漏关键信息），再优化精确度（剔除冗余内容）；一种安全的"轻触式"压缩是对"深历史中的工具调用与结果"进行清理。
    - Structed note-taking:
        - 定义：也称"智能体记忆"。智能体以固定频率将关键信息写入上下文外的持久化存储，在后续阶段按需拉回。
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

## MetaspolitAgent 架构（版本 1.0.0）
```
firstpentestAgent/
├── agent/                          # Agent实现层
│   ├── simple_agent.py              # SimpleAgent实现
│   ├── reconnaissance_planandsolve_agent.py  # Plan-and-Solve，驱动侦察阶段
│   ├── post_recon_react_agent.py    # ReAct，驱动Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation三阶段
│   ├── MetaspolitSimpleAgent.py
│   ├── models.py                    # Agent数据模型
│   └── state.py / state_manager.py  # Agent状态管理
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

## 记忆系统详细设计

### 如何设计记忆系统？
> 澄清场景，记忆分类，明确记忆的完整生命周期，反思与验证

- 强依赖场景：面向单用户还是多用户（涉及隔离和权限）？记忆需要跨会话还是只在单会话内？信息的更新频率如何，是偏静态的用户画像还是高频变化的任务状态？规模量级多大，是几百条还是千万级（决定要不要上向量库）？对准确性和延迟的要求哪个优先？
    - 面向单用户

    - **单用户 vs 多用户（隔离与权限）**：面向单用户场景，不涉及多租户之间的账号级权限隔离。但"单用户"不等于"无隔离需求"——同一操作者可能并行/串行执行多个 engagement（不同客户、不同 target），因此仍需要按 `engagement_id`/`target` 做逻辑边界，防止一次渗透中拿到的 credential、已知漏洞点串到另一个不相关的项目里，这是数据边界问题而非账号权限问题。

    - **单会话 vs 跨会话**：分记忆类型看待，不是统一答案。Working Memory 只在单 session 内有效（有 TTL/容量上限）；Episodic 和 Semantic Memory 必须跨会话持久化。原因是真实渗透往往跨越数小时到数天，中途会因为目标网络波动、RPC 超时、agent 进程重启等原因被迫拆分成多个 session——如果关键发现（资产、凭据、已验证的漏洞点）不能跨会话保留，就会在长任务里反复重复扫描、重复试错，甚至丢失刚拿到的突破口。

    - **更新频率（静态画像 vs 高频任务状态）**：以高频动态状态为主，静态部分占比小。Working/Episodic Memory 是渗透过程中的高频写入（每次扫描、每次 exploit 尝试都可能产生新记录）；Semantic Memory 更新频率低，是从大量 episodic 记录中周期性归纳出来的相对稳定的经验规则。本项目也没有典型 C 端场景下"用户兴趣画像"这类静态用户信息，取而代之的是客户 scope / Rules of Engagement 这类偏静态的约束条件——但这类信息是和 target/engagement 绑定的，而不是和"用户"本身绑定的，因此严格说不算传统意义上的用户画像。

    - **规模量级（决定是否上向量库）**：需要按记忆类型分层估算，而不是笼统给一个数量级。单次 engagement 产生的 Episodic Memory 量级大概率在几十到几百条（资产发现、凭据、exploit 尝试记录），即使长期跨多个 engagement 累积，大概率仍在万级以内，远达不到千万级；Semantic Memory 是归纳后的抽象规则，增长速度更慢，量级通常在百到千级。结论：当前阶段不需要为千万级规模设计独立的分布式向量数据库（如 Milvus/Pinecone），但 Episodic Memory 存在真实的语义检索需求（例如"这个 target 之前是否被扫描过类似的服务"这种非结构化匹配），因此仍值得引入轻量级、可嵌入的向量检索方案（如 SQLite + 本地向量索引，或 Chroma 这类嵌入式方案），而非重基础设施。

    - **准确性 vs 延迟**：准确性优先。渗透测试的核心特点是"单次记忆错误的代价很高"——如果检索时把一次失败的 exploit 误判为成功、或漏检了已经探明的凭据，轻则在长任务中重复动作浪费时间，重则触发目标 IDS/IPS 告警、打草惊蛇，甚至导致 engagement 被迫中止。这与强调实时响应的 C 端场景（客服对话、推荐系统）不同：pentest agent 每一步操作本身就有网络 RTT、exploit 执行时间（通常秒级到分钟级）作为基线开销，memory 检索多花的百毫秒到秒级延迟相对可忽略，但错误检索引发的连锁后果代价远高于这点延迟，因此设计上应优先保证召回与排序的准确性，而不是一味追求检索速度。

- 记忆分类与层次：提取时机、检索策略、存储介质、维护策略都会因记忆类型而异：
| 记忆类型 | 描述 |
|---|---|
| 工作记忆（Working Memory） | 相当于短期记忆，保存当前对话的上下文。容量被刻意限制（默认如 50 条）以保证低延迟访问，生命周期仅限于单次 session。 |
| 情景记忆（Episodic Memory） | 作用域限定在当前 engagement 内。记录一次渗透测试过程中产生的尝试、行动与结果，用于重建整个 engagement 生命周期的路线图，避免 agent 重复走无效路径。 |
| 语义记忆（Semantic Memory） | 用于模拟资深渗透测试人员积累的专业知识：从情景记录中提炼出的抽象、通用原则，以及可复用、可迁移的经验。 |
| 感知记忆（Perceptual Memory） | 处理图像、音频等多模态数据，支持跨模态检索，生命周期动态管理。 |

- 完整的生命周期: 提取/写入 -> 组织 -> 检索 -> 维护

- 记忆系统设计上的Trade-off/如何处理一些失败：记忆污染（错误信息被存下来后反复强化）、语义漂移（多轮摘要导致信息逐渐失真）、隐私问题（敏感信息该不该存、怎么删除、用户要求遗忘怎么办）。

### 记忆提取
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

### 记忆组织
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

### 记忆检索
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


### 记忆维护
- **记忆遗忘/淘汰（Memory Forgetting/Eviction）**：一套统一的遗忘机制
    - 四种遗忘策略：基于重要性、基于时间、基于容量、基于访问频率。
    - Working Memory 是唯一"自动"触发遗忘的类型：每次写入都会同时触发基于时间和基于容量的遗忘策略。
    - Episodic Memory 严格限定在 engagement 范围内，支持横向移动/权限提升场景下的因果链推理（跨越同一 engagement 内的多个 target）。因此这类记忆携带 `engagement_id` 检索边界。
        - 已解决（见「记忆检索」→ Episodic）：`engagement_id` 现在是唯一边界，检索方式是 LLM 驱动的结构化查找（target_ref/phase/causal_ref），而不是向量相似度——由于这条路径里已经不存在 embedding 匹配，跨 engagement 的污染也就不可能再通过 embedding 匹配溜进来。
        - 这类记忆不需要太在意去重、一致性或精炼。它的生命周期和 engagement 强绑定，事件触发式过滤在写入时就已经生效（只有少数几类符合条件的事件才会被转成一条记录），因此产生的量级从来不会大到需要花 LLM 资源去维护。完整、明确地记录每一次行动——无论成功还是失败——本身就是意义所在，也正是真实渗透测试人员的工作方式。
    - **Semantic Memory 维护**：语义记忆目前是通过汇总情景记忆生成的——这正是一致性、去重、精炼最重要的地方。设计意图是模拟资深渗透测试人员积累经验的过程，让 agent 具备持续自我提升的基础。这部分比其他记忆类型更难设计，目前也没有哪种方案能完全可靠地实现这个目标。需要周期性的 LLM 处理来精炼条目、检测矛盾、维持一致性并去重。
        - 去重是针对每一条新生成的语义记忆单独进行的：先用向量相似度做一轮粗筛，圈出候选集合，再交给 LLM 做去重判定。
        - 矛盾检测与一致性维护：候选集合的生成基于图（依托 Neo4j 实体图）——与新写入条目至少共享一个实体的其他记忆构成矛盾检测的候选集合，再交给 LLM 裁决。
            - 定义了一对语义记忆之间可能存在的四种关系，由 LLM 裁决：
            - duplicate（重复）：两条陈述本质上说的是同一件事，应当去重。
            - contradiction（矛盾）：在相同的前提/事件下（指最初触发这条记忆的情景事件），两条陈述得出互斥的结论；这需要矛盾消解处理，无法自动裁决时兜底转人工审核。
            - complementary（互补）：两条陈述相关但不冲突——各自独立成立且互相补充，因此都值得保留。
            - unrelated（无关）：两条陈述只是话题上相关，实际内容并无真实关联。
        - 精炼（Refinement）：这部分目前还没有设计。
    - **记忆巩固（Memory Consolidation）**：本质上仅限于把情景记忆巩固进语义记忆——把某个阶段积累的一批情景记录汇总进语义记忆。参照遗忘策略的思路，理论上可以设计基于重要性或基于访问频率的巩固策略，但这个想法目前还不够成熟，尚未列入实现计划。

## 如何应对上述问题？
记忆污染的风险可能比笔记里写的更值得重视。即使在同一个 engagement_id 边界内，也仍然可能出现跨目标串扰（cross-target bleed）——比如 Target A 上有效的凭据或成功的攻击手法，仅仅因为共享同一个 engagement scope，就被检索出来并错误地套用到 Target B 上；也可能出现信息过期（staleness）的情况——某个漏洞在 engagement 早期被记录为"可利用"，但期间目标可能已打补丁，或 IDS 规则被收紧，而这条过时记录却仍会被当作有效信息反复检索出来。

还有一个更贴合渗透测试场景、值得明确指出的污染途径：由于 episodic memory 是从工具/目标的返回数据中写入的，而目标环境本身是对抗性的，防御方或蜜罐完全可能故意提供误导性的服务 banner、伪造的凭据，或精心构造的响应，这些内容一旦被当作"事实"存下来，就会污染后续的推理——这更接近于"通过工具输出实施的 prompt injection"问题，而不是普通的记忆漂移。建议补充一点：检索/写入时应该以 target_id 为边界进行限定，而不仅仅是 engagement_id；同时，源自未经验证的目标响应的数据，其初始 confidence 应该低于 agent 自行验证过的结果。

关于confidence以及importance

## ContextBuilder 设计

### 设计动机与目标

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

## ReAct 阶段（Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation）× Context/Memory 融合设计

> `ContextBuilder`（GSSC 流水线）和 `MemoryExtractor`（事件触发抽取）此前只在 `agent/MetaspolitSimpleAgent.py`（文本正则式工具调用，非 Function Calling）里接了一半。`agent/post_recon_react_agent.py::PostReconReActAgent` 对应 PTES 除侦察外的三个阶段（威胁建模/漏洞分析 → 利用 → 后渗透），按本文档已确定的架构分工（ReAct 负责这三个阶段共通的 Thought→Action→Observation 循环），恰恰是最需要记忆系统的地方——一次失败的 exploit 尝试不能被遗忘、凭据要能跨 host 追溯、tech_fail/op_fail 要分清。本节记录如何让这两套系统与 ReAct 循环融合，并同步记录已落地的实现（`agent/post_recon_react_agent.py`、`core/agent.py`）。

### 阶段范围：从「仅利用阶段」扩展为 Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation 三阶段共用一个 Agent

- 最初落地时这个类叫 `ExploitReActAgent`，system prompt 里写死「当前处于 PTES 方法论的「利用」（Exploitation）阶段」，只覆盖 PTES 四阶段中的一个。
- **为什么合并**：按「Paradigms Chosen」一节的架构分工，Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation 三个阶段本来就都该用 ReAct（只有 recon 用 Plan-and-Solve）；且这个 Agent 本身不像 `PlanSolveAgent.Executor` 那样在代码里按阶段过滤工具（`search_module`/`get_module_info`、`run_module`/`set_option`、`execute_session`/`shell_upgrade` 等工具本来就注册在同一个 `ToolRegistry` 里，没有代码层面的阶段隔离），实际的阶段边界一直只靠 system prompt 文案约束——把三个阶段的文案都交给同一个类管理，比为每个阶段各开一个几乎同构的 Agent 子类更省重复代码。
- **怎么做**：`EXPLOIT_REACT_SYSTEM_PROMPT` 从一份固定文本改成 `POST_RECON_REACT_SYSTEM_PROMPT_TEMPLATE` + `_PHASE_INFO`（`{phase: {display_name, guidance}}`）字典；`_build_phase_system_prompt()` 在每次 `run()` 时按当时的 `self.state.ptes_phase` 现算对应措辞（未识别的阶段兜底退化为 `vuln_analysis`，即本 Agent 负责的第一个阶段）。构造时如果显式传入 `system_prompt`，则固定使用该文本、不再随阶段变化，供只想跑单一阶段的调用方使用。类名/文件名同步从 `ExploitReActAgent`/`agent/exploit_react_agent.py` 改为 `PostReconReActAgent`/`agent/post_recon_react_agent.py`。
- **阶段切换机制不变**：评估过"单次 `run()` 内部让 LLM 自主判断何时从 Threat Modeling/Vulnerability Analysis 推进到 exploitation 再到 post_exploitation"的方案（例如新增一个 AdvancePhase 工具），但这会削弱下一节「PTES phase 切换：触发权归编排层」这个既有安全设计——渗透测试里"要不要真的开始打这个漏洞""建立 session 后要不要继续深入"这类决策，希望编排层（或人工）在场，而不是完全交给模型在一次不间断的循环里自行决定。因此仍然沿用"编排层在阶段边界调用 `set_ptes_phase()`，再用同一个 Agent 实例重新调用 `run()`"的模式，只是现在编排层要在三个阶段边界都这样做，而不是只在进入/离开 exploitation 时做一次。

### 融合的基本原则：初始 Framing 用 ContextBuilder，循环内连续性用原生 messages

- ReAct 的 Thought→Action→Observation 循环在单次 `run()` 内部依赖 OpenAI Function Calling 协议维持的 `messages` 数组（assistant 的 `tool_calls` 必须紧跟对应 `tool_call_id` 的 `tool` 角色消息）——这段短期连续性不能也不需要被 `ContextBuilder` 取代。
- `ContextBuilder.build()` 的角色是**任务开始前的一次性 framing**：`PostReconReActAgent._build_initial_messages` 在 `run()` 最开始调用它，把 `AgentState`、`engagement_id` 传进去，取回结构化的 `[State]/[Evidence]/[Context]/[Output]` 文本作为 user 角色的首条消息内容，让 LLM 在第一步 Thought 之前就看到本次 engagement 已发现的资产/凭据（episodic `task_state`）和相关经验（semantic `related_memory`）。
- **实现细节**：`system_prompt` 仍然独立作为 system 角色消息（角色/策略约束不变），调用 `ContextBuilder.build()` 时故意把 `system_instructions` 传 `None`——如果连同 `system_prompt` 一起传给 `ContextBuilder`，会在返回文本的 `[Role & Policies]` 分区里把角色设定重复注入一遍，浪费 token 预算。
- 不需要每一步循环都重新调用 `ContextBuilder.build()`——那样会导致 token 预算迅速超支，且和 Function Calling 的多轮协议冲突。循环内临时需要再查一次记忆的需求，交给下一节。

### 循环内的按需检索：MemoryTool 是一个普通工具，不是每步重跑 GSSC

- `tools/builtin/memory_tool.py::MemoryTool` 本身就是一个 `BaseTool`，注册进 `PostReconReActAgent` 的 `tool_registry` 后，和 `search_module`/`run_module` 等业务工具没有区别——不需要任何额外接线代码。
- LLM 在 ReAct 循环中间如果需要临时确认"这个漏洞点是不是之前试过"，可以像调用其他工具一样主动调用 `memory(action=search, ...)`，产生一次 Action→Observation，符合 ReAct 自身的推理节奏。`POST_RECON_REACT_SYSTEM_PROMPT_TEMPLATE` 里补充了「记忆工具的使用」一节，明确告诉模型这个能力的存在与用法。
- 分工边界很明确：`ContextBuilder` 负责"任务开始时框架性地把已知信息摆在桌面上"，`MemoryTool` 负责"循环中 LLM 觉得需要时主动查"。两者不重叠、不冲突。

### Observation → Memory 写入：每次工具结果之后无条件走 MemoryExtractor

- `PostReconReActAgent._run_impl` 里，每次业务工具执行完（拿到 `result_text` 之后、追加进 `messages` 之前），都会调用 `self._record_tool_observation(...)`。
- **实现落地**：这段"懒加载 MemoryExtractor + 调用 log_working_memory/maybe_extract_episodic"的逻辑没有直接写在 `PostReconReActAgent` 里，而是提炼成了 `core/agent.py::Agent._get_memory_extractor` / `Agent._record_tool_observation` 两个基类方法（见本节末尾「复用点」）。
- **调用规范**：传给 `_record_tool_observation` 的 `output` 是工具的完整原始结果文本（`result_text = str(result.output) if result.success else ...`），不做任何截断/摘要——`memory/extraction.py::_judge_episodic_event` 判断 tech_fail vs op_fail 的依据往往就在具体报错文本里，提前摘要会让 LLM judge 丢失分类依据。
- tech_fail/op_fail 的区分逻辑本身不需要在 `PostReconReActAgent` 里重新实现，已经在 `_EPISODIC_JUDGE_PROMPT` 里完整实现。

### target_ref 要落到 host 粒度，不能照抄 `state.target.address`

- `PostReconReActAgent._extract_target_ref` 优先从当前工具调用的实际参数（`RHOSTS`/`RHOST`/`target`/`host`/`ip`/`address` 等常见 key，覆盖 `run_module`/`set_option` 等工具的标准选项名）里提取具体 host 地址，取不到才兜底退回 `state.target.address`。
- 原因：exploitation/post_exploitation 阶段的因果链（凭据取自主机 A、用于登录主机 B）天然是 host 级别的，如果 `target_ref` 统一退化成顶层 target 地址，会丢失这个粒度，`causal_ref` 也失去意义。

### Causal chain：从"状态自动追踪"调整为"LLM 驱动 + memory_id 可见"

- 最初设想的实现路径是纯状态驱动：给 `Credential`/`Session` 加 `origin_memory_id` 字段，在 `state.target.sessions`/`credentials` 前后 diff 出新增对象时自动同步写入并回填该字段，`causal_ref` 完全由 Agent 自己在 state 里追踪出来，不靠 LLM 猜。
- **为什么没有按这个路径完整实现**：核对代码后发现这条路径依赖的上游数据目前并不可靠——`metasploit/session.py::SessionsAPI.list()` 返回的是原始 RPC `dict`，而不是 `agent/models.py::Session` 结构化实例；`tools/builtin/list_sessions.py` 把这个 dict 直接整体赋给 `state.target.sessions`（每次调用整体覆盖，不是增量更新），且 `AgentState.target` 默认是 `None`。当前工具集里也没有任何一个"凭据发现"工具会产出 `Credential` 对象。在这些基础设施没有补齐之前，做"diff state 里的 Session/Credential 对象"这一步只是在一个不可靠的数据源上叠加一层同样不可靠的因果推断，不如不做。
- **实际采用的方案**：`origin_memory_id` 字段本身仍然按原计划加到了 `Credential`/`Session`（`agent/models.py`），作为面向未来的数据模型钩子；但因果链的**触发**改为 LLM 驱动——
    1. `tools/builtin/memory_tool.py::_search_memory` 的每条结果现在会带上完整的 `memory.id`（此前只在内容预览里看不到 id）；`_add_memory` 的确认文本也从截断的 `ID: {memory_id[:8]}...` 改成完整的 `ID: {memory_id}`。
    2. `POST_RECON_REACT_SYSTEM_PROMPT_TEMPLATE` 明确指引模型：记录一条新的 episodic 事件（如"用凭据 X 登录了主机 B"）时，如果这个事件依赖于之前已经见过的某条记忆（如"凭据 X 发现于主机 A"的搜索结果或写入确认里的 id），把该 id 通过 `causal_ref` 参数带上，并强调"不要自己编造 id"。
- 这个方案牺牲了"完全确定性"（依赖 LLM 正确复述 id），换来的是**现在就能跑通**，且不依赖尚未存在的凭据发现工具或尚未修复的 session 数据管道。等 `list_sessions`/凭据工具把结构化的 `Session`/`Credential` 对象真正接上 `state.target` 之后，最初设想的状态驱动路径可以作为更精确的补充机制叠加上去（`origin_memory_id` 字段已经就位，不需要再改数据模型）。

### PTES phase 切换：触发权归编排层，Agent 只暴露 hook

- `core/agent.py::Agent.set_ptes_phase(state, new_phase, target_ref)` / `Agent.finalize_engagement(state, phases, target_ref)` 是两个通用的基类方法（不假设 `self.state` 存在，`state` 由调用方显式传入），内部调用 `MemoryExtractor.consolidate_phase_async`/`finalize_engagement` 完成阶段边界触发的 semantic 归纳。
- `PostReconReActAgent.set_ptes_phase(new_phase)` / `finalize_engagement()` 是对应的薄封装，自动把 `self.state` 和当前 `target_ref` 传进去，对外保持和 `MetaspolitSimpleAgent` 一致的调用方式。
- `PostReconReActAgent` 不会在 `run()` 内部自动判断"现在是不是该切阶段了"——它可能被上层多次调用，每次只负责当前一步任务（Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation 三者之一），阶段切换的触发时机留给编排层（未来的顶层 orchestrator，或当前调用方脚本）显式调用这两个方法。

### `⚠️ REPLAN_NEEDED` 信号要同时落一条 episodic 记忆

- `POST_RECON_REACT_SYSTEM_PROMPT_TEMPLATE` 新增「计划偏差上报」约定，与 `RECON_EXECUTOR_SYSTEM_PROMPT` 保持一致的标记格式：模型在 `Finish` 的 `answer` 开头加 `⚠️ REPLAN_NEEDED: <原因>`。
- `_run_impl` 在算出 `final_answer` 后检查这个前缀，命中则调用 `_record_replan_signal`，**同步**（不经过 `maybe_extract_episodic` 的异步 LLM 判断）写一条 `event_type=defense_observed` 的 episodic 记忆，`content` 前缀按 `self.state.ptes_phase` 从 `_PHASE_INFO` 取当前阶段的中文名（"威胁建模/漏洞分析阶段计划偏差: ..."/"利用阶段计划偏差: ..."/"后渗透阶段计划偏差: ..."），不再像单一阶段时那样写死"利用阶段"。之所以不走异步判断路径：这个信号本身已经是 LLM 明确判断过的"计划失效"事实，不需要再让另一个 LLM 判断"这算不算一个事件"；同步写入也保证这条记录在 `run()` 返回前就已经落库。

### Token 预算分工：ContextBuilder 的压缩策略不覆盖 ReAct 循环内的增长

- `ContextBuilder._compress()` 目前是"超预算就硬截断"（见上「Compress」小节），这是已知局限，非高保真摘要。
- `ContextBuilder.build()` 只在 `run()` 开始时调用一次，只压缩它自己生成的那段初始 framing 文本；循环内 `messages` 的增长交给 `max_steps` 上限 + 达到上限后的兜底收尾（`_run_impl` 里 `final_answer is None` 时退回一次不带工具的 `llm.invoke`），而不是无限增长。循环内高保真压缩留作后续 Context Engineering 优化项。

### 复用点：三个 Agent 共用同一套记忆接线方法

- `_extract_memories`/`_get_memory_extractor` 这套逻辑原来写死在 `MetaspolitSimpleAgent` 一个类里。落地时把它提炼成了 `core/agent.py::Agent` 基类上的共享方法：
    - `Agent._get_memory_extractor()`：懒加载 `MemoryExtractor`，复用 `tool_registry.get_tool("memory")` 拿到的 `MemoryManager`。
    - `Agent._record_tool_observation(tool_name, arguments, output, tool_success, target_ref, phase, session_id)`：统一的"写 working + 触发 episodic"入口。
    - `Agent.set_ptes_phase(state, new_phase, target_ref)` / `Agent.finalize_engagement(state, phases, target_ref)`：见上一节。
- `MetaspolitSimpleAgent` 和 `PostReconReActAgent` 都只负责各自"怎么算出 `target_ref`"（前者用 `state.target.address`，后者按 host 粒度提取，见前文），懒加载与写入路径完全共用，不再各写一份。
- 这几个方法都不假设 `self.state` 存在（`state`/`target_ref` 由调用方显式传入），所以不依赖记忆系统的 Agent（如纯对话的 `SimpleAgent`）不受影响，`Agent.__init__` 也只新增了 `self.engagement_id = None` 和 `self._memory_extractor = None` 两个属性，不改变任何现有构造函数签名。

## 侦察阶段 Plan-and-Solve × Context/Memory 融合设计

> 同一套融合思路（ContextBuilder 做一次性 framing、Observation 无条件写记忆、REPLAN_NEEDED 落记忆、phase 切换 hook、共用基类方法）落地到 `agent/reconnaissance_planandsolve_agent.py::PlanSolveAgent`（PTES 侦察阶段，`Planner` + `Executor` 两段式）。落地过程中顺带修好了 `Executor._execute_step` 里"临时借用一个 `SimpleAgent` 实例复用工具调用逻辑"的 hack——那条路径依赖的 `SimpleAgent._build_tool_schemas`/`_execute_tool_call` 两个方法在仓库里根本不存在，之前是完全跑不通的死代码。

### 和 ReAct 的关键差异：Plan-and-Solve 每一步都是从零构建的独立 messages

- ReAct 的融合设计能"只在 run() 开始时调用一次 ContextBuilder"，是因为循环内的连续性由 Function Calling 协议维持的 `messages` 数组负责——后续步骤天然能看到前面的内容。
- Plan-and-Solve 不是这样：`Executor.execute()` 里每一步都会重新拼一个全新的 `messages`（`system_prompt` + 手工格式化的 `context` 字符串，包含原始问题/完整计划/历史步骤结果/当前步骤），互相之间没有共享的对话状态。
- 因此"只查一次记忆"的原则在这里换了一种实现方式：`PlanSolveAgent.run()` 在最开始调用一次 `_build_memory_context()`，把返回的 `memory_context` 字符串分别传给 `Planner.plan()`（生成计划前看一眼，用于规划阶段避免安排重复扫描）和 `Executor.execute()`（原样透传，由 `Executor` 在**每一步**的 `context` 拼接里重复嵌入同一份文本）。是"只查一次、多处复用同一份结果"，不是"只让第一步看到"。

### Planner 侧：memory_context 作为规划前的独立 user 轮次

- `Planner.plan()` 新增 `memory_context` 参数，构造 messages 时插在 `system_prompt` 和"请为以下问题生成详细的执行计划"之间，作为独立的一条 user 消息，不与问题文本拼接在一起。
- `Planner` 本身不需要、也不能接入 Function Calling 意义上的 `memory` 工具调用——它的 `tool_choice` 被强制指定为 `generate_plan`（`{"type": "function", "function": {"name": "generate_plan"}}`），单次请求内无法先调用 `memory` 再被强制调用 `generate_plan`。ContextBuilder 的一次性预取，就是这里"规划前查记忆"的唯一入口。

### Executor 侧：直接用 ToolRegistry，不再借用 SimpleAgent

- 原实现在 `_execute_step` 里 `from .simple_agent import SimpleAgent` 临时构造一个 `temp_agent`，调用 `temp_agent._build_tool_schemas()` / `temp_agent._execute_tool_call()`——这两个方法在 `SimpleAgent` 类里都不存在，属于之前从未跑通过的死代码。
- 现在改为直接调用 `self.tool_registry.to_function_schemas()`（见上文「复用点」，与 `PostReconReActAgent` 共用同一个 `ToolRegistry` 方法）构建 schema，以及 `self.tool_registry.execute_tool(tool_name, state, **arguments)` 执行工具，不再需要借助任何 Agent 实例。
- `state: AgentState` 现在被显式一路透传：`PlanSolveAgent.run()` → `Executor.execute(question, plan, state, ...)` → `_execute_step(context, state, ...)` → `execute_tool(tool_name, state, ...)`。此前 `Executor` 根本不持有/不传递 `state`，`nmap_scan` 等工具的 `state` 形参永远收到 `None`。

### Observation → Memory 写入：回调而不是直接继承

- `Executor` 不是 `Agent` 子类（它是 `PlanSolveAgent` 内部的纯协作对象，没有 `tool_registry`/`llm` 之外的 Agent 语义），不能直接调用 `Agent._record_tool_observation`。
- 设计上用一个回调解耦：`Executor.__init__` 新增 `on_tool_observation: Optional[Callable[[str, Dict, str, bool], None]]` 参数，`PlanSolveAgent.__init__` 构造 `Executor` 时把 `self._on_tool_observation` 传进去；每次工具执行完，`Executor._execute_step` 调用这个回调，`PlanSolveAgent._on_tool_observation` 再转手调用继承自 `Agent` 基类的 `_record_tool_observation`。
- `target_ref` 提取按侦察阶段实际的工具集调整：`nmap_scan` 的目标参数名是 `target`（而不是利用阶段 `run_module`/`set_option` 用的 `RHOSTS`），`PlanSolveAgent._extract_target_ref` 按 `("target", "TARGET", "host", "ip", "address", "RHOSTS")` 的顺序尝试提取，取不到才兜底到 `state.target.address`。

### `⚠️ REPLAN_NEEDED` 落记忆：event_type 用 `recon_negative`

- `RECON_EXECUTOR_SYSTEM_PROMPT` 本来就已经有这个标记的书面约定（"目标不可达、出现计划外的主机/服务"等），但此前代码里没有任何地方真正检查这个前缀、做点什么——只是写在提示词里但没人消费。
- `PlanSolveAgent.run()` 在 `executor.execute()` 返回后检查 `final_answer` 是否以 `⚠️ REPLAN_NEEDED:` 开头，命中则调用 `_record_replan_signal`，同步写一条 episodic 记忆。
- `event_type` 选择 `recon_negative` 而不是利用阶段用的 `defense_observed`：侦察阶段的偏差通常是"预期的资产/结果没有按计划出现"（目标不可达、扫描到计划外网段等），语义上更贴近"侦察阶段的阴性/异常结果"这个既有分类，而不是"遭遇主动防御"。

### 记忆工具的使用：从"禁止列表"到"允许列表"外单独说明

- `RECON_EXECUTOR_SYSTEM_PROMPT` 原本只有一份利用类工具的禁止清单。新增的「记忆工具的使用」一节明确 `memory` 工具不在禁止之列，并给出侦察阶段的具体理由：查询目标是否已经扫描过，避免对同一目标重复执行有真实网络开销的扫描——这是侦察阶段区别于利用阶段的记忆使用场景（利用阶段更强调 `causal_ref` 因果链，侦察阶段更强调"别重复扫"）。

### 已删除：`arun_stream`

- `PlanSolveAgent.arun_stream`（及 `SimpleAgent.arun_stream`）曾是一条独立于 `Planner`/`Executor` 的流式实现，直接调用 `self.llm.astream_invoke` 手写 prompt。但 `PentestAgentLLM`（`core/llm.py`）从未实现过 `astream_invoke` 这个方法，且全仓库没有任何调用方使用这两个 `arun_stream`——它们属于未完成、也从未被使用过的死代码，一调用就会因为方法不存在而 `AttributeError`。已连同相关的未使用 import（`StreamEvent`/`StreamEventType`/`AsyncGenerator`/`LifecycleHook`）一起删除；如果之后要做流式输出，建议基于已有的同步 `run()`/`invoke_with_tools()` 路径重新设计，而不是恢复这条半成品实现。
