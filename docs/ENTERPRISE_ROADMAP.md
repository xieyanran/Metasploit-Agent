# Enterprise Roadmap

> Version: 0.1.0
>
> Status: Draft
>
> Purpose: Define the path from the current single-operator Metasploit agent prototype to an enterprise-grade agent platform, while keeping Metasploit as the only integration for now. This document does not introduce new integrations (Nessus, Burp, etc.) — it hardens and restructures what already exists.

---

# Where This Project Is Today

An honest gap assessment, file-by-file, before proposing changes.

| Area | Current State | Gap |
|------|---------------|-----|
| Orchestration | The hand-written `agent/reasoning` + `agent/llm` ReAct loop has been retired; `main.py` now builds the agent with `langchain.agents.create_agent`, wrapping the same `agent/tools/*.py` implementations via [agent/langchain_tools.py](../agent/langchain_tools.py) | No `recursion_limit` set on `agent.invoke(...)` yet — nothing bounds how many tool-calling turns the agent can take |
| State | [agent/state.py](../agent/state.py) — in-memory `@dataclass` tree, still read/written by tools directly (unchanged by the LangChain switch) | Lost on crash/restart; no persistence; no way to resume an engagement |
| Tool registry | Two parallel implementations: [agent/tool_registry.py](../agent/tool_registry.py) (used by `main.py`) and [agent/tool_manager.py](../agent/tool_manager.py) (more complete, unused) | Dead/duplicate code, unclear which is canonical |
| Planner | [agent/planner/](../agent/planner/) implements a `TaskGraph` + hardcoded `EXPLOIT_WORKFLOW` | Not wired into `main.py` or the reasoning loop — multi-step planning isn't actually used yet |
| Config & secrets | Read ad hoc from `os.environ` in [main.py](../main.py), with a hardcoded fallback `MSF_RPC_PASS=123456` | No central config object, no fail-fast validation, weak default credential shipped in source |
| Logging | None — `grep` for `import logging` across the repo returns nothing; `main.py` uses `print()` | No record of what the agent did, in what order, or why |
| Authorization / scope | None — the agent will act on whatever `Target` it's given | Nothing stops the agent from touching a host outside an authorized engagement |
| Audit trail | `HistoryState` in `agent/state.py` keeps tool calls in memory only | No durable, tamper-evident record of exploit actions taken — this is normally a hard requirement for pentest tooling |
| Approval gates | None — `run_module` / `execute_session` fire as soon as the reasoner picks them | No human checkpoint before an actual exploit or session interaction runs |
| Error handling | `metasploit/exceptions.py` defines `RPCConnectionError`, `RPCTimeoutError`, `AuthenticationError`, but callers mostly let them propagate uncaught | No retries, no graceful degradation, one flaky RPC call can kill a run |
| Tests | [tests/tool_tests](../tests/tool_tests) and [tests/rpc_test](../tests/rpc_test) cover individual tools and RPC login/logout | No tests for the reasoning loop, state transitions, or (once built) the governance layer; no CI |

This isn't a criticism of the prototype — it's exactly what a fast first pass should look like. The point of this roadmap is to close these gaps deliberately rather than accumulate them.

---

# Target Architecture

```text
                ┌───────────────────────────┐
                │   Interface                │   CLI today (main.py) → service later
                └──────────────┬─────────────┘
                               ▼
                ┌───────────────────────────┐
                │   Governance Layer  (NEW)  │   scope allowlist, approval gates,
                │                            │   audit log — sits in front of every
                │                            │   tool execution, not just the LLM
                └──────────────┬─────────────┘
                               ▼
                ┌───────────────────────────┐
                │   Orchestration            │   langchain.agents.create_agent
                │   (main.py,                │   (+ Planner, not yet wired in)
                │    agent/langchain_tools)  │
                └──────────────┬─────────────┘
                               ▼
                ┌───────────────────────────┐
                │   Tool / Plugin Layer      │   single BaseTool contract,
                │   (agent/tools)            │   one registry (not two)
                └──────────────┬─────────────┘
                               ▼
                ┌───────────────────────────┐
                │   Integration Clients      │   metasploit/ package —
                │                            │   the only integration for now
                └──────────────┬─────────────┘
                               ▼
                ┌───────────────────────────┐
                │   Persistence               │  engagement state + audit store
                └──────────────┬─────────────┘
                               ▼
                ┌───────────────────────────┐
                │   Observability             │  structured logs, metrics
                └───────────────────────────┘
```

The key structural change from today: the **Governance Layer** is new and sits between orchestration and tool execution — every tool call passes through scope-check → (maybe) approval → execute → audit-log, regardless of which tool it is. This is what turns "an LLM with exploit access" into something an enterprise security team could actually sign off on.

---

# Four Pillars

## Pillar 1 — Engineering Hygiene

| Workstream | What changes |
|---|---|
| Central config | Replace ad hoc `os.environ.get(...)` calls in `main.py` with a single `agent/config.py` (e.g. a validated dataclass or `pydantic-settings`) that fails fast on startup if required values are missing, and drops the hardcoded `123456` fallback password |
| Structured logging | Introduce `logging` (JSON formatter) across `agent/`, `metasploit/`; replace the `print()` calls in `main.py`; log every RPC call, tool execution, and reasoning decision at appropriate levels |
| Retries & error handling | Wrap `MetasploitRPCClient.call` in a retry-with-backoff for `RPCConnectionError` / `RPCTimeoutError`; the LangChain tool wrappers in `agent/langchain_tools.py` currently let tool exceptions propagate instead of turning them into a `ToolResult` the agent can reason about |
| Loop termination guard | Pass a `recursion_limit` via `agent.invoke(..., config={"recursion_limit": N})` — right now nothing bounds how many tool-calling steps `create_agent`'s graph can take |
| Remove duplication | Pick one of `ToolRegistry` / `ToolManager` (recommend keeping `ToolManager` — it already has `unregister`, `list_tools`, and error handling on unknown tool names) and delete the other |
| CI | GitHub Actions workflow running `pytest` on push/PR; currently there's no CI at all |
| Test expansion | Add tests for `ReasoningLoop`, `AgentState` transitions, and (once built) the governance layer — today's tests only cover individual tools and RPC auth |

## Pillar 2 — Safety & Governance

This is the pillar to prioritize first. The project can already execute real exploits against real hosts with zero authorization checks, zero audit trail, and zero approval step — that's the biggest gap between "prototype" and something an enterprise security org would allow near a real engagement.

| Workstream | What changes |
|---|---|
| Scope enforcement | An explicit, engagement-level allowlist (authorized hosts/CIDR ranges) checked before *any* tool executes — not just at `main.py` startup. A tool call against an out-of-scope target should fail closed with a clear error, not silently proceed |
| Audit trail | Append-only, durable log of every tool invocation: tool name, parameters, target, result, timestamp, and (once there's a caller identity) who initiated it. This formalizes and replaces the in-memory-only `HistoryState` |
| Approval gates | A human-in-the-loop confirmation step before "Action" category tools fire (`run_module`, `execute_session`, `kill_meterpreter_session` — per the Observation/Action split already defined in [docs/TOOL_INTERFACE.md](TOOL_INTERFACE.md)). Should be configurable per engagement, but on by default |
| Kill switch | A way to immediately halt an in-progress engagement/reasoning loop from outside the loop itself |
| Credential hygiene | MSF RPC credentials sourced from a secrets store or env-only (no defaults in code), and the RPC connection itself should move off `SSL=false` (see `README.md`) for anything beyond local dev |

## Pillar 3 — Extensibility Architecture

| Workstream | What changes |
|---|---|
| Single plugin boundary | `BaseTool` in [agent/tools/base.py](../agent/tools/base.py) is still the contract every tool implements; `agent/langchain_tools.py` is the only place that knows about LangChain, so the orchestration framework stays swappable without touching tool logic |
| Wire the planner in | [agent/planner/planner.py](../agent/planner/planner.py) exists but nothing calls it yet — `create_agent`'s built-in ReAct loop still does single-step tool selection only. A real planner would sit above it (e.g. as LangChain middleware, or driving multiple `agent.invoke()` calls) to make multi-step workflows (recon → module selection → exploitation → post) explicit instead of left to the LLM's own judgment each turn |
| Governance via middleware | `create_agent(..., middleware=[...])` is the natural hook for Pillar 2 (scope check / approval gate / audit log) — implement it as `AgentMiddleware`, not as changes scattered across each tool |
| Keep Metasploit isolated | `metasploit/` is already cleanly separated from `agent/` — preserve that boundary so a future non-Metasploit integration is "add a new tool set," not "touch the orchestration layer" |

## Pillar 4 — Deployment & Multi-Tenancy

Deliberately last — this only makes sense once Pillars 1–3 make a single engagement trustworthy end-to-end.

| Workstream | What changes |
|---|---|
| Persistence | Move `AgentState` and the audit log behind a repository interface, backed by SQLite (single-node) or Postgres (shared), instead of the current in-memory dataclasses |
| Service layer | Wrap `ReasoningLoop` behind an API (e.g. FastAPI) with an explicit "engagement" concept, replacing the current single `main.py` script entry point |
| Engagement isolation | One `AgentState` + one Metasploit workspace per engagement — no shared global state across concurrent users |
| Containerization | A `Dockerfile` for the agent, with documented connectivity to an external MSF RPC endpoint |
| Service auth | AuthN/authz for *who can start/stop an engagement* — distinct from the in-engagement scope enforcement in Pillar 2 |

---

# Phasing

```text
Phase 0  Cheap fixes, unblock everything else
         - loop termination guard
         - remove ToolRegistry/ToolManager duplication
         - central config, drop hardcoded default password

Phase 1  Safety & Governance
         - scope allowlist
         - audit trail
         - approval gate on Action tools
         (do this before adding more exploit-capable tools —
          risk grows with capability, guardrails should come first)

Phase 2  Engineering Hygiene hardening
         - structured logging
         - retries around RPC calls
         - CI + expanded test coverage

Phase 3  Extensibility
         - wire the Planner into the reasoning loop
         - finalize the single plugin registry

Phase 4  Deployment & Multi-Tenancy
         - persistence layer
         - service/API wrapper
         - containerization
```

Phases are ordered by risk reduction per unit of effort, not by how "impressive" the result looks — Phase 1 doesn't add a single new capability, it makes the existing capability safe to use.

---

# Explicit Non-Goals (for now)

- No new integrations beyond Metasploit (Nessus, Burp, etc.) — stays out of scope until Metasploit support is solid
- No multi-tenant SaaS-style user/org auth system before Phase 4
- No unattended autonomous exploitation without an approval gate — Pillar 2 makes human-in-the-loop the default, not opt-in

---

# Open Decisions

These need a decision before Phase 1 implementation starts, since they change the shape of the governance layer.

| Decision | Options |
|---|---|
| Approval gate scope | Require approval for every Action tool, or make it configurable per engagement/tool? |
| Audit log destination | Local append-only file, embedded DB (SQLite), or forward to an external system (SIEM/log pipeline)? |
| Scope definition | Single host/CIDR allowlist per engagement, or something richer (port/service-level scoping)? |
| Deployment horizon | Does this stay a single-operator CLI tool indefinitely, or is Phase 4 (service) a real near-term target? |

---

# Version History

| Version | Changes |
|---------|---------|
| 0.1.0 | Initial roadmap draft |
