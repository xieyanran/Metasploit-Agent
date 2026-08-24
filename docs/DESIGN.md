# Metasploit Agent Design(version 1.0.0)

English | [简体中文](DESIGN.zh-CN.md)

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

The current design follows the industry-standard PTES methodology (Intelligence Gathering → Threat Modeling/Vulnerability Analysis → Exploitation → Post-Exploitation). The reconnaissance stage uses a Plan-and-Solve architecture (`agent/reconnaissance_planandsolve_agent.py::PlanSolveAgent`) to produce a detailed exploitation plan up front. Every subsequent stage uses a ReAct architecture, dynamically adjusting the original plan as new information emerges — concretely, a single `agent/post_recon_react_agent.py::PostReconReActAgent` instance is reused across all three stages (Vulnerability Analysis, Exploitation, Post-Exploitation): the orchestrator calls `set_ptes_phase()` at each stage boundary and re-invokes `run()`, and the agent renders a phase-specific system prompt from `state.ptes_phase` each time (see「ReAct 阶段 × Context/Memory 融合设计」below). The agent never decides on its own when a stage ends — that authority stays with the orchestrator:

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
Still on the roadmap for future development.

### Context Engineering
What context configuration is most likely to make the model produce the behavior we want?
During inference, how do we curate and maintain the "optimal set of information (tokens)" — not just the prompt itself, but everything else that enters the context window.

- Why Context Engineering matters
    - Context rot: as the number of tokens in the context window grows, the model's ability to accurately recall information from that context actually declines. Context should therefore be treated as a resource subject to diminishing marginal returns.

- Goal: use as few tokens as possible, but with the highest possible signal density, to maximize the probability of getting the desired outcome.

- Context Engineering components
    - System Prompt: the language should be clear and direct, with the level of detail pitched "just right." Two common failure modes sit at opposite extremes:
        - Over-hardcoding: encoding complex, brittle if-else logic directly into the prompt, which is costly to maintain and easily breaks.
        - Over-vague: giving only high-level goals and generic guidance.
        - Recommendation: organize the prompt into sections (e.g., `<background_information>`, tool guidance, output description, etc.), delimited with XML/Markdown.
    - Tools:
        - Tools define the contract between the agent and its information/action space, and must promote efficiency: they should return token-efficient information while also encouraging effective agent behavior.
            - Single responsibility, minimal overlap between tools, and clear interface semantics;
            - Robust to errors;
            - Parameter descriptions that are precise and unambiguous, making full use of the model's strengths in expression and reasoning.
    - Examples (Few-shot): providing examples is always recommended — for an LLM, a good example is worth a thousand words.

- Context engineering for long-horizon tasks:
    - Compaction:
        - Definition: as a conversation approaches the context limit, produce a high-fidelity summary of it and restart a new context window with that summary, preserving long-range coherence.
        - Practice: have the model compress the conversation while preserving architectural decisions, unresolved issues, and implementation details, discarding repetitive tool output and noise; the new window carries the compressed summary plus a small set of recent, highly relevant artifacts (e.g., "the handful of files accessed most recently").
        - Tuning advice: optimize for recall first (make sure nothing critical is lost), then for precision (trim redundant content); one safe, "light-touch" form of compaction is cleaning up tool calls and results from deep history.
    - Structured note-taking:
        - Definition: also called "agentic memory." The agent writes key information to persistent storage outside the context window at a fixed cadence, and pulls it back in as needed in later stages.
        - Value: maintains persistent state and dependency relationships at very low context cost. For example, maintaining a TODO list, a project NOTES.md file, or an index of key conclusions/dependencies/blockers lets the agent preserve progress and consistency across dozens of tool calls and multiple context resets.
        - Note: this is equally effective outside coding scenarios (e.g., long-horizon strategic tasks, or goal tracking and stat-keeping in games/simulations). Combined with the MemoryTool from Chapter 8, this can easily be implemented as file-based or vector-based external memory, retrieved at runtime.
    - Sub-agent architectures:
        -

### Context Engineering && Memory System 

| Dimension | Context Engineering | Memory System |
|---|---|---|
| Focus | How to organize the set of tokens fed to the model for a single inference call | How information is extracted, classified, stored, retrieved, and maintained over time |
| Core question | "What should go in the context window right now?" | "Where does this information come from, should it be kept, for how long, and how is it retrieved later?" |
| Scope | Runtime strategy at the level of a single LLM call | System-architecture design spanning sessions and engagements |
| Goal | Maximize the probability of getting the desired output using as few tokens as possible with the highest signal density | Let the agent persistently retain assets/credentials/experience, avoiding redundant scans and repeated trial-and-error over long-running tasks |
| Typical components/techniques | System Prompt, Tools, Few-shot, Compaction, Structured note-taking | Extraction timing, organizational granularity, retrieval strategy, and forgetting/consolidation mechanisms across the four memory layers — Working/Episodic/Semantic/Perceptual |
| Relationship | Constrains what form and density Memory's retrieval results must take before entering the context window (conclusion summaries plus structured tags, rather than raw records) — otherwise causing context rot | Supplies Context Engineering with a reusable long-horizon knowledge layer; Structured note-taking is, in essence, a memory mechanism that "writes to persistent external storage at a fixed cadence and pulls it back in as needed" |

In one sentence: Context Engineering is a general-purpose information-governance discipline for a single inference call; Memory System is the storage/retrieval/maintenance subsystem that, in this penetration-testing context, is factored out specifically to handle "which information needs to persist across sessions." Memory supplies Context with long-horizon knowledge, while Context Engineering, in turn, constrains the form in which Memory's output enters the model's inference window.

## MetaspolitAgent Architecture(version 1.0.0)
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

## DeSign Memory System

### how to design the Memory System?
> Clarify the scenario, classify memory types, define the complete memory lifecycle, and build in reflection and verification.

- Scenario-dependent design questions: Is this single-user or multi-user (which bears on isolation and permissions)? Does memory need to persist across sessions, or only within a single session? How frequently does the underlying information change — is it closer to a static user profile, or fast-changing task state? What scale is expected — hundreds of entries or tens of millions (which determines whether a vector store is warranted)? And which matters more, accuracy or latency?

    - **Single-user vs. multi-user (isolation and permissions)**: This is a single-user scenario. Isolation is still required, however — across different engagements, and across different targets within an engagement (when there is more than one).

    - **Single-session vs. cross-session**: This needs to be considered per memory type, mirroring the human memory system — some memories are transient and exist only within a single session. Real-world penetration tests, however, typically span hours to days and are often forcibly split across multiple sessions, whether due to RPC timeouts or agent process restarts. Memories of key asset discoveries and milestone results therefore need to persist across sessions.

    - **Update frequency**: Dominated by high-frequency, dynamic state, with only a small static component. Memory updates center on changing task state; this project also has none of the static user information and preferences — e.g., a "user interest profile" — typical of consumer-facing scenarios.

    - **Scale**: Needs to be estimated per memory type in a tiered fashion, rather than assigning one blanket order of magnitude.

    - **Accuracy vs. latency**: Accuracy matters more. The defining trait of penetration testing is that a single memory error is costly — it can waste time, or worse, trigger defensive measures and force the engagement to abort. This differs from consumer-facing scenarios that prioritize real-time responsiveness, such as customer-service chat or recommendation systems. The design should therefore prioritize recall and ranking accuracy over retrieval speed.

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
> When to extract memory
> How to determine which parts of a conversation should be extracted and stored as memory, and which memory type they should be stored as

- **The Timing**: Design trade-offs for extraction timing. In HelloAgents this is left entirely to the model's own judgment.
    - **Industry reference**: The timing strategies actually used by mainstream open-source pentest agent projects converge on a small set of patterns.
        - **PentAGI**: Automatically compresses earlier history as the context approaches its limit — i.e., a **capacity/window trigger**.
        - **VulnBot**: The Summarizer only runs on PTES phase transitions (reconnaissance → scanning → exploitation), summarizing key conclusions and passing them to the next phase — i.e., a **phase-transition trigger** — and it only produces conclusion summaries rather than processing every turn.
        - **mem0** (currently the most widely adopted general-purpose memory layer, reused directly by a large number of agent projects): Fundamentally extracts on every turn, but the extraction runs **asynchronously and does not block the main loop** (`add()` is called after each turn, while LLM extraction, deduplication, and write-back run in the background), and it follows an **ADD-only** policy (append-only, no in-place edits or deletes) to avoid premature merging that would lose information. This is the key technique for solving the "per-turn extraction is too expensive" problem — not by abandoning per-turn extraction, but by moving it off the critical path into an async process.

    - **Approach**:
        1. Working memory: Written directly to memory automatically, bypassing the LLM.
        2. Episodic memory: Triggered after every conversational turn, submitted to the LLM to judge whether it qualifies as episodic memory. ADD-only — old records are never overwritten, since both a failed exploit attempt and a subsequent successful one should be preserved, so the causal chain of the attack path can be reconstructed during a post-mortem. A more economical approach would be to train a small, dedicated model for this task; the initial idea was event-triggered timing using regular expressions to classify each event, but that proved too rigid to classify accurately.
        3. Semantic memory: Triggered at PTES phase boundaries, distilling the episodic memories accumulated during that phase into generalized conclusions; as a fallback, one more distillation pass runs at the end of the engagement. No additional importance-scoring mechanism is needed, since phase boundaries are themselves a low-cost, naturally occurring trigger point. This follows the mainstream open-source project VulnBot.
        4. Perceptual memory keeps its existing "process on evidence arrival" behavior unchanged.

- **Storage classification by memory type**: Relates to the design of `_classify_memory_type` in `memory/manager.py`

    - **Working Memory criteria**: The default destination for new content. Valid only within the current session, and further bounded within the session by a TTL/capacity limit.

    - **Episodic Memory criteria**: Persists across sessions, bound to one-off events tied to a specific target/session, e.g.:
        - New assets: discovered hosts/ports/services/versions
        - New credentials or secrets
        - Exploit attempts and their outcomes (the reason for failure must be distinguished: technical failure [vulnerability absent/already patched] vs. operational failure [network unreachable, payload encoding error, RPC timeout], to avoid misclassifying an operational failure as "this technique doesn't work against this environment")
        - Negative reconnaissance results: closed ports, services that don't match any known exploit, etc., to avoid re-scanning the same target next time
        - Discovered defensive measures on the target
        - Key milestones related to privilege escalation/lateral movement, and cross-asset causal chains (e.g., "credential X was obtained from host A and used to log into host B") — recording dependency relationships along the attack path rather than isolated events
        - OSINT/passive intelligence: one-off discoveries tied to the target, such as subdomains, leaked code repositories, or social-engineering leads
        - Scope and client-imposed constraints (tightly bound to the target, so classified as Episodic; rules/techniques that are target-independent and reusable across engagements belong in Semantic instead)

    - **Semantic Memory criteria**: Persists across sessions, detached from any specific target — more abstract, reusable knowledge, concepts, and rules.
        - Test: "would this still be useful against a different target?" — content qualifies for Semantic only if it still holds after being detached from the specific target/session, and can be decomposed into entities and relations (e.g., CVE ↔ affected service version, exploit module ↔ prerequisites, technique ↔ detection/defense measure)
        - Technical characteristics and trigger conditions of vulnerabilities/CVEs
        - The applicability boundaries and failure conditions of exploit modules (e.g., architecture requirements, defense configurations under which they typically fail) — such patterns are usually generalized from multiple episodic failure records, rather than drawn directly from a single attempt
        - Techniques for analyzing and confirming vulnerabilities
        - General strategies for privilege escalation/lateral movement
        - Best practices and known pitfalls for tool usage
        - General techniques for defense evasion (EDR/AV/WAF)
        - Sources include not just direct judgments from a single conversational turn, but also generalizations distilled from multiple episodic memories (corresponding to `find_patterns`/`consolidate_memories` in the code)

    - **Perceptual Memory criteria**: Non-text evidence such as screenshots, packet captures, or audio, originating from external tools that aren't otherwise integrated.

### Memory Organize
- Granularity: one memory, one MemoryItem, comprising:
    - memory id
    - memory type
    - user id (not applicable in a single-user scenario; reserved as an extension field for a future multi-user agent)
    - timestamp
    - importance
    - content
    - metadata

- MetaData Schema:
    > Design principle: metadata should hold only structured keys used for "filtering / retrieval / lifecycle decisions."
    > Layered design: a common layer (shared across all four memory types) plus type-specific layers (needed only by episodic/semantic/perceptual respectively).

    - **Common layer** (shared by working/episodic/semantic/perceptual):
        - `session_id` (str, required for working/episodic/perceptual, optional for semantic): session identifier
        - `engagement_id` (str, required for episodic, recommended for working/perceptual, optional for semantic): engagement-level scope identifier
        - `target_ref` (str, recommended for episodic and perceptual): asset-level identifier (IP/host)
        - `phase` (enum: `recon`/`vuln_analysis`/`exploitation`/`post_exploitation`): aligns with the PTES phase
        - `is_target_bound` (bool): the classification criterion distinguishing episodic from semantic
        - `updated_at` (int, timestamp): time of last modification
        - `last_accessed_at` (int, timestamp): time of last retrieval hit

    - **Episodic-specific**:
        - `event_type` (enum, currently 8 values: asset_discovery/credential_found/exploit_attempt/recon_negative/defense_observed/privesc_lateral_move/osint_finding/scope_directive)
        - `outcome` (enum: `success`/`tech_fail`/`op_fail`/`negative`): the outcome of the event
        - `causal_ref` (list[str], pointing to other episodic memory_ids): records dependency relationships along the attack path

    - **Semantic-specific**:
        - `entities` (list[str]): the entities involved in this piece of knowledge — e.g., CVE identifiers, exploit module names — fed into the Neo4j knowledge graph
        - `confidence` (float 0-1): distinct from `importance`, which answers "how important is this piece of knowledge," `confidence` answers "how trustworthy is this piece of knowledge." A rule generalized from a single episodic sample and one generalized from 10 repeated failures may both score high on importance, yet differ in confidence.
        - `derived_from` (list[str], pointing to the episodic memory_ids it was generalized from): traces which episodic records this semantic knowledge was consolidated from

    - **Perceptual-specific**:
        - 正在开发中

- Update semantics: different memory types follow different update strategies, detailed under Memory Maintenance design.
    - Working Memory uses overwrite-style update semantics.
    - Episodic Memory uses an Add-Only policy, keeping it auditable and traceable.
    - Semantic Memory is not simply limited to either pure overwrite or pure append; the details are covered in Maintenance.

- Memory partitioning: memories are split into separate storage areas by the classification above, with each area independently configuring its own retrieval, maintenance, and other policies.

### Memory Retrieval
> The retrieval strategy is not designed independently — it is derived from the characteristics already fixed in the "Memory Taxonomy and Hierarchy" section.

- **Working Memory retrieval strategy: thinking && design**
    - Scale: dozens of entries — essentially a small-window ranking problem, so introducing a vector database isn't warranted.
    - Retrieval boundary: within the same `session_id`, which recent context is most relevant to the current step.
    - Ranking score: temporal recency should be the dominant factor, combined with an importance weight and keyword hits.

- **Episodic Memory retrieval strategy: thinking && design**
    - No vector database, no semantic recall: the most critical parts of episodic content — CVE identifiers, version numbers, host names — cannot be precisely measured by vector similarity; having the LLM read the raw text directly is more accurate.
    - **Retrieval boundary**: `engagement_id` is the sole boundary. Fuzzy, cross-engagement queries like "have we seen something similar before" are handled entirely by Semantic Memory retrieval — a natural extension of the classification criterion already established ("would this still be useful against a different target?"): episodic memory only answers "what happened within this engagement."
    - Retrieval flow: the LLM first queries Semantic Memory (recalling similar situations/experience and reasoning about possible attack chains — once a RAG system is introduced, this can also serve as a reference), and then, based on that, the LLM determines the specific metadata parameters to run as a SQL query.
    
- **Semantic Memory retrieval strategy: thinking && design**

    - **Retrieval boundary**: there is no hard filtering boundary at all — a natural extension of the classification criterion already established ("would this still be useful against a different target?").

    - **Dual-path recall + fused ranking**: two independent relevance signals are recalled separately, then merged into a single ranking.
        - Semantic relevance: this kind of fuzzy matching is handled by vector similarity.
        - Same technical object: the same CVE, the same service, the same exploit module.
        - In this case, vector-based retrieval and entity-relationship-based graph retrieval each independently recall a batch of candidates, which are then merged.
        - Fused ranking: relevance itself, combined with importance and confidence.

    - **Handling contradictions**: Semantic Memory consists of experiential rules generalized from multiple Episodic records, and conclusions generalized in different batches can end up contradicting each other. Rather than simply deleting or overwriting the older conclusion, the design flags both sides of the conflict: if a more reliable alternative conclusion exists in the candidate set, the flagged, conflicting one is filtered out; if it is the only candidate (no alternative available), it is kept, but the "this is disputed" signal is passed to the LLM to decide for itself whether to trust it.

    - **失败兜底**：图检索异常/超时不能阻塞向量检索的返回，两路独立 fail-open，保证最差情况下退化为"纯向量检索"，而不是整个 retrieve() 抛异常返回空。

    - 检索前的 query 联想扩展（让 LLM 先把 query 联想成候选关键词再检索）评估过但暂不引入，复杂度和当前阶段的收益不匹配，先把上面几项落地、有实际检索数据后再重新评估。

- **Perceptual Memory 检索策略的思路**
    - 正在开发中

- 量化指标:
    - Precision@k / Recall@k：在返回的前 k 条里算准确率和召回率，最基础。
    - 记忆污染抵抗力（见下方「How to deal with the problem?」+ [`benchmarks/MEMORY_POISONING.md`](../benchmarks/MEMORY_POISONING.md)）：19-20 条/8 组量级的 case，每条跑 3 次取均值±标准差（不是单次点估计——LLM 判断本身有波动，标准差本身就是"结果稳不稳"的证据）：
        - IAR (Injection Acceptance Rate)：对抗性 tool_output（伪造凭据/伪造 scope_directive/劝退式虚假结论/角色扮演劫持/不带攻击腔调的技术性伪造等 7 类手法）里，攻击者注入的虚假事实被 episodic judge 采信并计划落库的比例。越低越好。
        - BRR (Benign Recall Rate)：对照的真实合法事件仍被正确捕获的比例，和 IAR 一起看——防止"修复"变成"把什么都拦掉"式的假胜利。
        - CTAR (Cross-Target Attribution Rate)：只按 engagement_id 检索时，返回文本能否机械地区分每条结果属于哪个 target_ref。
        - CCG (Confidence Calibration Gap)：语义归纳时，"多个不同 target 独立印证"相对"单一 target 灌水"，置信度是否有正向差距。
        - UCSR (Unreviewed Contradiction Slip-through Rate)：手动写入的矛盾 semantic 记忆，有多大比例绕过矛盾检测、原样以自报高置信度可检索。越低越好。
        - DPR (Downstream Poisoning Rate)：和 IAR 的区别——IAR 测"假话有没有被存进去"，DPR 测"已经存进去的假话，会不会真的通过检索→拼进 context（真实的 `ContextBuilder` 流水线）→影响 Agent 对后续问题的实际决策"。IAR=0% 不代表 DPR 也低，这是两个独立的攻击面。


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

还有一个更贴合渗透测试场景、值得明确指出的污染途径：由于 episodic memory 是从工具/目标的返回数据中写入的，而目标环境本身是对抗性的，防御方或蜜罐完全可能故意提供误导性的服务 banner、伪造的凭据，或精心构造的响应，这些内容一旦被当作"事实"存下来，就会污染后续的推理——这更接近于"通过工具输出实施的 prompt injection"问题，而不是普通的记忆漂移。

另有一条更根本的风险：以上都在测"写入"这一步——假话有没有被骗着存进去。存进去之后，这条被污染的记忆还会不会真的通过检索被拼进 Agent 下一次决策的 context、进而影响其实际建议？这条链路（`context/builder.py::ContextBuilder`）此前完全没被测过，也正是公开研究里 MINJA/AgentPoison 等针对 LLM Agent 记忆/RAG 的投毒攻击实际攻击的东西。

已实现并量化（完整方法论、case 设计、样本量/统计口径、可复现步骤见 [`benchmarks/MEMORY_POISONING.md`](../benchmarks/MEMORY_POISONING.md)）：

| 风险点 | 对应指标 | 修复 | Before → After |
|---|---|---|---|
| 跨目标串扰：检索结果不带 target 归属，Target A 的凭据/结论容易被误用到 Target B | CTAR | `tools/builtin/memory_tool.py::_search_memory` 的格式化结果里显式打印 target_ref | 0% → 100%（8 组场景） |
| 通过工具输出实施的 prompt injection：目标/蜜罐构造的误导性内容被 episodic judge 当作事实采信 | IAR / BRR | `memory/extraction.py::_EPISODIC_JUDGE_PROMPT` 用显式分隔符包裹不可信数据，加入"只能当观察数据、不能当指令"的免疫提示 | IAR 15.8%±37.5%→10.5%±31.5%，BRR 56.7%±49.7%→55.0%±51.0%（19-20 条 case ×3 trials，无回归） |
| 置信度只看归纳所依据的样本数，单一（甚至敌对的）target 灌水和多 target 独立印证算出一样高的置信度 | CCG | `memory/extraction.py::_consolidate_phase_job` 置信度公式改为主要由来源 target 多样性驱动，样本量只给很小权重 | +0.000 → +0.269（相对提升 68%） |
| 手动写入（Agent 通过 memory 工具直接 add）的 semantic 记忆完全绕开去重/矛盾检测，自报高置信度即可原样可检索 | UCSR | `MemoryTool._add_memory` 补一次 `SemanticMemoryMaintainer.maintain()`（仅在传入 `llm` 时启用，不引入硬依赖） | 100%±0.0% → 50.0%±53.5%（8 组场景 ×3 trials——只对约一半场景稳定生效，见下方诚实局限） |
| 已成功写入的假记忆，经检索拼进 context 后是否真的带偏 Agent 的实际决策 | DPR | `context/builder.py::_structure` 的 `[Evidence]` 部分补一条免疫提示：confidence 是写入方自报的分数、不是独立核实过的结果，单条未经印证的记忆不应被当作已证实的事实 | 16.7%±25.2% → **4.2%±11.8%**（8 组场景 ×3 trials，人工复核后判断真实残余风险更接近 0%，见下方诚实局限） |

其中 confidence（源自未经验证的目标响应的数据，应低于 agent 自行验证过的结果）目前由 CCG（来源多样性影响置信度）和 DPR 对应的这条修复（读取端不默认信任自报置信度）两条共同覆盖，单条 episodic 记录本身是否"已验证"尚未建模为独立字段——留作后续工作。

诚实局限（详见 benchmarks/MEMORY_POISONING.md 对应小节）：
- UCSR 的 50%±53.5% 说明矛盾检测对"结论直接对立"的场景很有效，但对措辞更接近、只在某个限定条件上矛盾的场景经常失手（例如被判成"重复"而合并，而不是识别为矛盾）。
- DPR 的量化过程本身暴露过一次判分方法的 bug：最初按"整篇回答里有没有出现过 marker"判分，结果把"结论里正确拒绝采纳、但在依据部分如实引用了这条记忆用于说明推理过程"的回答也算成"被带偏"，修复后测出的 75% 因此虚高。改成只看"1. 结论"这一节后重新量化，"修复前"也是 16.7%（不是 75%），"修复后"降到 4.2%，人工复核全部 48 组回答后判断这条残余多半也是同样的"引用但拒绝"被误判，真实风险更接近 0%——这个判分方法上的自我纠错过程本身记录在 MEMORY_POISONING.md 里，是这次量化里最值得注意的一个教训：机械字符串匹配的判分逻辑本身也需要针对性验证，不能假设"包含即采信"。

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
