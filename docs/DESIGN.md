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

### Memory Extraction
> 提取记忆的时机
> 如何判断哪些对话应该被提取储存为memory,该被储存为哪种类型的memory
> 如何维护记忆的一致性，如果有记忆冲突如何处理
> 如何进行去重
> 如何处理记忆过时的情况

- The Timing: 
    

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

- **分类判定机制（`memory/manager.py: _classify_memory_type`）**：不再对自由文本做关键词匹配（原来的`_is_episodic_content`/`_is_semantic_content`是照抄HelloAgents的占位实现，命中"昨天/定义"这类关键词，对渗透场景不适用），改为让候选记忆携带结构化字段，分类基于字段直接判定：
    - 结构化字段：
        - `is_target_bound: bool` —— 是否绑定具体target/engagement，**episodic vs semantic 的唯一决定性开关**
        - `target_ref: Optional[str]` —— `is_target_bound=True` 时应提供
        - `event_type: enum` —— 复用上面 Episodic 8类 / Semantic 8类 判据作为枚举值，仅用于**辅助校验**（与`is_target_bound`矛盾时告警），不参与决定分支，避免两套判据互相打架
        - `entities: Optional[List[str]]` —— 若已能提取实体，供semantic的"能否拆解为实体关系"约束校验
    - 判定逻辑：
        ```
        def _classify_memory_type(content, metadata) -> str:
            if metadata.is_target_bound is None:
                return "working"          # 未提供结构化信号，不强行分类
            if metadata.is_target_bound:
                return "episodic"
            else:
                if not metadata.entities:
                    warn("semantic候选无可识别实体，知识图谱部分将退化为纯向量检索")
                return "semantic"
        ```

