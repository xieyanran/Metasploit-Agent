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

### Instruction template(system_prompt)
1. personal
2. Available Tools
3. Output format
4. Important Tips

### Memory System Design
> Memory System mechanism的必要性：当前到LLM设计上是无状态的，所以模型可能会因为上下文窗口的限制丢失早期重要信息，Agent无法记住用户的个性需求与偏好，从过往成功与失败的经验的学习能力受限，可能在多轮对话中可能出现不一致的回答，所以我们的框架需要引入记忆系统. 
> 对渗透测试这个垂直场景而言，记忆系统的必要性更加突出：一次真实渗透往往跨越数小时甚至数天、涉及多个目标主机与攻击面，Agent 必须记住已发现的资产、凭据、漏洞点和已尝试过的payload，否则会在**长任务**中重复扫描、重复试错，甚至遗忘关键突破口
> 同时不同目标环境（防御强度、合规边界、历史成功利用链）差异很大，需要靠情景记忆/语义记忆沉淀"这类环境下哪些手法有效的**经验**，才能让 Agent 在下一次任务中做出更贴合该特定目标的决策，而不是每次都从零推理。
> 我们根据认知心理学的研究进行设计，人类的记忆分为感知记忆，工作记忆，以及长期记忆。
> 参考了HelloAgents开源项目的记忆系统的设计

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
    - 渗透测试场景
    - 面向单用户
    - 记忆需要跨会话
    - 对准确性要求更优先



### Memory Extraction
> 提取记忆的时机
> 如何判断哪些对话应该被提取储存为memory,该被储存为哪种类型的memory
> 如何维护记忆的一致性，如果有记忆冲突如何处理
> 如何进行去重
> 如何处理记忆过时的情况

- **The Timing**：提取时机的设计取舍，HelloAgents里是纯靠模型自主判断。

    - **逐轮提取（每轮对话后即时提取）**
        - 好处：信息新鲜时提取，语义最准确；即使进程崩溃/连接中断也不会丢失关键发现——这点对渗透测试尤其重要，一次渗透可能持续数小时到数天，中途因目标网络波动、RPC超时、agent进程重启而丢失未提取的working memory，可能意味着丢失刚拿到的credential或刚探明的漏洞点
        - 代价：每轮都调用LLM做分类抽取，成本和延迟显著上升；渗透测试中大量轮次是"侦察噪音"（单次端口扫描的中间输出、多次重试的网络报错），逐轮提取容易产生大量低价值甚至重复的记忆条目，加重去重与一致性维护的负担
        - 是否适配渗透测试终极目标：部分适配。逐轮提取解决了"长任务不能丢关键发现"的及时性问题，但没解决"哪些轮次值得提取"这个更关键的问题——不加区分地逐轮提取，本质是用成本换安全性，不是最优解

    - **事件触发式（Event-triggered）**——更适合作为episodic memory的主要时机
        - 触发条件可直接复用下文已定义的Episodic Memory边界：新资产发现、新凭据、exploit尝试出结果（成功/技术性失败/操作性失败）、阴性侦察结果、防御机制被发现、权限提升关键节点等
        - 好处：既保证"事件发生即写入"的及时性，又天然对齐"什么值得记住"的业务语义边界，减少无意义中间轮次带来的记忆噪音
        - 实现上可用规则/正则做轻量触发（工具返回中匹配到session established、credential pattern、CVE编号等），再配合一次轻量LLM调用做归类与摘要，而非对每轮都做完整LLM抽取

    - **容量/窗口触发式**（参考MemGPT的分层内存驱逐思路）
        - 当working memory达到容量上限（默认50条）或临近上下文窗口极限时，强制触发一次"驱逐"式提取——把即将被淘汰的内容筛选、升级为episodic/semantic memory后再丢弃
        - 这是working memory→episodic/semantic晋升机制里必须存在的兜底时机，否则容量限制本身就会造成信息丢失

    - **重要性阈值触发**（参考Generative Agents的reflection机制）
        - 给每条working memory打一个"重要性分数"（如利用成功=高、常规扫描回显=低），当近期事件的重要性累计分数超过阈值才触发一次提取/反思，而非逐轮触发
        - 相比纯规则的事件触发，能捕捉规则未覆盖但语义上重要的信息，代价是需要额外的打分机制

    - **阶段转换触发**（Phase/milestone-triggered）
        - 与"Current Design"中PTES各阶段划分天然契合：每次从侦察→漏洞分析→利用→后渗透切换阶段时，触发一次批量提取/整理
        - 好处是节奏可预测、便于复盘；但阶段之间跨度可能长达数小时，若只等阶段结束才提取，阶段内的关键发现仍有中途丢失风险——通常需与事件触发结合使用，不宜单独作为唯一时机

    - **周期性/后台整理式（Consolidation）**——semantic memory的主要来源
        - 类似人类睡眠时的记忆巩固：定期（如每积累N条episodic memory，或每次engagement结束）异步跑一次归纳，把多条episodic memory中反复出现的规律提炼为semantic memory（例如"某exploit模块在开启ASLR的目标上多次失败" → 归纳为该模块的适用边界）
        - 语义记忆的定义本身就是"跨多次episodic记忆归纳出的抽象规则"，不可能靠单轮/单事件提取产生，必须是回顾式、批量式的（对应`find_patterns`/`consolidate_memories`）

    - **业界参考**：主流开源pentest agent项目实际用的时机比上面理论列举的更收敛，只组合了其中两三种
        - **PentAGI**（MIT开源、可自托管）：working context / episodic history / long-term vector store三层，用"chain summarization"在上下文快超限时自动压缩较早历史——即**容量/窗口触发**
        - **VulnBot**（Planner/Memory Retriever/Generator/Executor/Summarizer五模块）：Summarizer只在PTES阶段切换（侦察→扫描→利用）时工作，摘要关键结论并传递给下一阶段——即**阶段转换触发**，且只做结论摘要，不逐轮处理
        - **mem0**（当前最主流的通用记忆层，被大量agent项目直接复用）：本质是逐轮提取，但提取过程**异步执行、不阻塞主循环**（`add()`在每轮后调用，LLM抽取/去重/写库在后台跑），且采用**ADD-only**策略（只增不改/不删），避免过早合并导致信息丢失。这是解决"逐轮提取成本太高"问题的关键手段——不是不逐轮，而是把它挪到异步

    - **最终方案**：
        1. Working memory：自动直写，不经过LLM，也不需要等agent主动调用memory工具
        2. Episodic memory：复用已有`_classify_memory_type`的事件规则做轻量触发，命中后**异步**跑一次LLM摘要归档，不阻塞agent下一步动作；ADD-only，不覆盖旧记录——一次失败的exploit尝试和后续成功的尝试都应保留，便于复盘攻击路径的因果链
        3. Semantic memory：PTES阶段边界触发，对该阶段积累的episodic memory做一次归纳提炼；兜底在engagement结束时再跑一次`consolidate_memories`，不需要额外的重要性打分机制（阶段边界本身就是低成本、天然存在的触发点）
        4. Perceptual memory维持"证据到达即处理"不变

- **记忆类型的储存判断**：涉及memory/manager.py/中def _classify_memory_type的设计
    - 首先，记忆类型的描述:
| Memory Type | Description |
|---|---|
| Working Memory | 扮演“短期记忆”的角色，主要用于储存当前对话的上下文信息，为确保高速访问和响应，其容量被有意限制（例如，默认50条），并且生命周期与单个会话绑定。 |
| Episodic Memory | 进行“复盘”和学习过往经验的基础。负责存储具体的交互事件与学习经历。并且支持回顾式检索。 |
| Semantic Memory | 存储的是更为抽象的知识，概念和规则，这部分类型的记忆类型具有高度的持久性。 |
| Perceptual Memory | 专门处理图像，音频等多模态信息，并支持跨模态检索。其生命周期会进行动态管理。 |

    - Working Memory判断: 默认进入,仅在当前的session中有效，并且在session内部还有TTL/容量边界
    - 如何将working memory的有效信息升级为Episodic Memory\Semantic Memory, 当然也可以自主创建，参考Pentest agent 论文（PentestAgent/AutoPen/APT-Agent 等）普遍采用"静态知识 vs 动态环境信息"的二分——静态、预训练/沉淀下来的网络安全通用知识（漏洞机理、攻击手法）走长期记忆，动态的、每步产生的观测/推理走短期记忆，且部分系统会把渗透知识按 service/OS/CVE/rank 等结构化属性索引。
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

- **记忆的维护**：
    - **记忆的Consistency**:
    - **记忆去重**:
    - **记忆遗忘/淘汰**:
        - working memory会有TTL自动过期
        - working memory会有容量上限淘汰

### Memory Retrievel


