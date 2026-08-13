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
面向长时程任务的上下文工程


## MetaspolitAgents Architecture(version 1.0.0)
hello-agents/
├── tests/
│  
├── core/                     # 核心框架层
│   ├── agent.py              # Agent基类
│   ├── llm.py                # HelloAgentsLLM统一接口
│   ├── message.py            # 消息系统
│   ├── config.py             # 配置管理
│   └── exceptions.py         # 异常体系
│   
├── agents/                   # Agent实现层
│   ├── simple_agent.py       # SimpleAgent实现
│   ├── react_agent.py        # ReActAgent实现
│   ├── reflection_agent.py   # ReflectionAgent实现
│   └── plan_solve_agent.py   # PlanAndSolveAgent实现
│   
├── tools/                    # 工具系统层
│   ├── base.py               # 工具基类
│   ├── registry.py           # 工具注册机制
│   ├── chain.py              # 工具链管理系统
│   ├── async_executor.py     # 异步工具执行器
│   └── builtin/              # 内置工具集
│       ├── calculator.py     # 计算工具
│       └── search.py         # 搜索工具
└── memory/

## DeSign Memory System

### how to design the Memory System?
> 澄清场景，记忆分类，明确记忆的完整生命周期，trade-off以及失败处理

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

- Trade-off:

- 如何处理一些失败：记忆污染（错误信息被存下来后反复强化）、语义漂移（多轮摘要导致信息逐渐失真）、隐私问题（敏感信息该不该存、怎么删除、用户要求遗忘怎么办）。

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
    - user id
    - timestamp
    - importance
    - content
    - metadata

- MetaData Schema:
    > 设计原则：metadata 只放"用于过滤/检索/生命周期判断"的结构化 key，参考 VulnBot 的 Summarizer 只产出"结论摘要 + 少量结构化标签"而不是原始工具输出，PentAGI 的三层 context 也只在层间传递压缩后的摘要。
    > 分层设计：通用层（四类记忆共享）+ 类型特有层（仅 episodic/semantic/perceptual 各自需要）。

    - **通用层**（working/episodic/semantic/perceptual 共用）：
        - `session_id` (str, 自动写入)：归属会话，已在 `memory_tool.py` 实现
        - `engagement_id` (str, episodic 必填/其余可选)：项目级作用域标识，比现有的 `target_ref` 高一层——一次 engagement 可能涉及多个 target，拆成两个字段能同时支持"查这个项目下所有记录"和"查这台主机下所有记录"两种检索粒度，呼应"单用户但需要 engagement 级隔离"的结论
        - `target_ref` (str, episodic 建议填)：资产级标识（IP/host），沿用已有字段
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

- 更新语义: 追加式还是覆盖式，覆盖式简单省空间，但丢失历史、无法回溯、出错难排查；追加式（保留旧版本，标记为已取代）可审计、可回滚，但需要额外的版本管理和空间成本。

- 记忆分层: 将记忆按照之前的分类，分成不同的存储区，每个区独立配置检索，维护等策略。

### Memory Retrievel
> 检索策略不是独立设计的，而是由"记忆分类与层次"一节里已经确定的特征反推出来的。

- **Working Memory 检索策略的思路**
    - 要回答的问题是"当前 session 里，和当前这一步最相关的近期上下文是什么"，本质是小窗口内的排序问题，不是大规模语料库里的召回问题——容量被限制在几十条量级，穷举都不算贵，谈不上"找不找得到"，只有"怎么排"。
    - 核心矛盾不是召回率，是优先级：越新的信息通常越贴近当前动作（agent 刚执行完的工具调用结果，比十轮前的扫描日志更可能影响下一步），所以时间近因应该是主导因子，语义相似度只是辅助排序，不是召回手段。
    - 不引入向量库这类重基础设施，是"规模量级决定检索方案"这条原则（见"如何设计"一节）在 working memory 上的直接体现——规模到不了向量检索的门槛，加进来只是白白多一层延迟和维护成本。

- **Episodic Memory 检索策略的思路**
    - 检索边界: 以engagement_id为边界。
    - 要回答两类性质不同的问题：一类是精确边界问题（"这条记忆是不是这次 engagement / 这台 target 的"），一类是模糊语义问题（"有没有类似情形之前遇到过"）。这两类问题不能靠同一种机制解决——精确边界必须靠结构化字段硬过滤，模糊语义必须靠相似度软召回，思路上要先用 engagement_id/target_ref/phase 圈出安全边界，再在边界内做语义召回，而不是反过来。一旦语义检索把跨 target 的记忆误召回排到前面，就违反了"单用户但需要 engagement 级隔离"这条硬约束（见"如何设计"一节），这不是排序不理想，是信息串错了 target，代价没法靠"检索后降权"弥补，必须在召回阶段就被结构化边界挡住。
    - 排序要同时看重要性和时间，但两者不能合成一个笼统分数：情景记忆记录的是"发生过的事"，越久之前的发现越可能因为 target 环境变化（打了补丁、改了配置）而失效，新近发现天然更可信；但重要性不该被新旧完全取代——刚拿到的 credential 和三个月前拿到但仍然有效的 credential 都很重要，不该只因为时间久远被压到后面。所以"这条记忆有多重要"和"这条记忆有多可能仍然成立"要分开考虑。
    - 语义检索的意义在于覆盖结构化过滤到不了的场景："这个 target 之前是否被扫描过类似的服务"这种问题没有固定字段能精确匹配，只能靠内容相似度召回，这也是"如何设计"一节里提出"值得引入轻量级向量检索方案"的原因。

- **Semantic Memory 检索策略的思路**
    - 语义记忆存的不是孤立事实，而是"实体+关系"（CVE↔受影响服务、exploit↔前置条件），要回答的问题也分两种形态：一种是"和这个概念相关的知识有哪些"（主题层面的模糊匹配，向量检索擅长），另一种是"从这个已知点出发，沿关系链能推到哪些确定性结论"（如"已知目标跑的是这个服务版本，有没有已知能用的 exploit"——这是精确多跳推理，向量相似度天然做不到，因为"服务版本"和"exploit 模块"在语言层面未必相似，两者的关联是人为定义的因果/适用关系，不是语义相近性）。
    - 因此两条检索通路要互补而非二选一：向量负责"语义相近"，图负责"关系确定"，覆盖的是完全不同的信息缺口，合并结果时也不能无差别混合——一条知识如果只被向量检索命中、没有关系佐证，说明它可能只是主题相关但因果关系未必成立，检索层面需要保留这种区分。
    - 语义记忆是从多条情景记忆归纳出来的抽象规则，检索时还要考虑"这条知识有多可信"，区别于"这条知识有多重要"——只从一次失败样本归纳出的规则，和从十次重复失败归纳出的规则，检索排序理应给不同权重，这呼应"Memory Organize"一节里把 confidence 和 importance 拆成两个独立字段的设计。

- **Perceptual Memory 检索策略的思路**
    - 原始内容（截图、流量包、音频）本身没有可供关键词或结构化字段直接匹配的文本语义，检索天然只能走相似度这一条路——这是数据形态决定的，不是设计取舍的结果。
    - 理想情况下应支持跨模态检索（用文字描述找截图），但这依赖专门的跨模态编码器（如 CLIP/CLAP）；在没有引入这类模型之前，检索范围只能收窄到同模态内比较，这是当前能力边界带来的临时取舍，不是长期设计目标——一旦跨模态编码可用，检索思路应自然扩展到跨模态查询，不需要重新设计这一层。
    - 这类记忆是"证据"而非"结论"，排序上除了语义相似度，还要看召回的证据是否仍然新鲜、和当前排查的 target/session 是否对应——时间和归属关系是重要的辅助过滤维度，不能只靠相似度分数。

- 量化指标:
    - 召回率: 


### Memory Maintence
- **Memory Forgetting/Eviction**: a unified forgetting mechanism
    - Four forgetting strategies: importance-based, time-based, capacity-based, and access-based.
    - Working Memory is the only type with "automatic" triggering: every write triggers both the time-based and capacity-based forgetting strategies.
    - Episodic Memory is tightly scoped to the engagement, supporting causal-chain reasoning for lateral-movement/privilege-escalation scenarios (spanning multiple targets within the same engagement). Accordingly, this memory type carries an `engagement_id` retrieval boundary.
        - This may still be susceptible to memory contamination.
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

    



