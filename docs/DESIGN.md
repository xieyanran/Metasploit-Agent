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


### Instruction template(system_prompt)
1. personal
2. Available Tools
3. Output format
4. Important Tips









