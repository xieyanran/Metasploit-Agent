# Metasploit Pentest Agent

An LLM agent that drives real penetration tests through the Metasploit Framework — reconnaissance, threat modeling, vulnerability analysis, exploitation, and post-exploitation — instead of a static scan-and-report script.

## Why an agent, not a script

Past the fingerprinting stage, a single service usually matches several candidate exploit modules, and there's no fixed rule for ranking them or deciding when to abandon a failing approach — that judgment call is exactly what a static if/else pipeline can't encode. This project follows the industry-standard [PTES methodology](https://en.wikipedia.org/wiki/Penetration_test) (Intelligence Gathering → Threat Modeling / Vulnerability Analysis → Exploitation → Post-Exploitation), but hands the moment-to-moment judgment calls to an LLM reasoning core instead of hard-coded branches:

- **Reconnaissance is Plan-and-Solve.** It's the structured phase — the agent drafts a full task list up front (`agent/reconnaissance_planandsolve_agent.py`), then executes it step by step.
- **Everything after recon is ReAct.** Threat Modeling, Vulnerability Analysis, Exploitation, and Post-Exploitation reuse a *single* `PostReconReActAgent` instance across all four phases — the orchestrator calls `set_ptes_phase()` at each boundary and the agent re-derives a phase-specific system prompt from `state.ptes_phase` on every `run()`. A Thought → Action → Observation loop fits this part well, because each step's outcome genuinely changes what the next move should be.
- **A four-tier memory system** (Working / Episodic / Semantic / Perceptual) carries discovered assets, credentials, and past exploit attempts across a single long-running engagement — real engagements span hours to days, and without it the agent would re-scan and re-try things it already knows.
- **Every tool call that touches a real target is gated by a human-authored scope guard** (`core/scope.py`): the LLM never decides for itself what's in scope. `scope.json` is a plain JSON file a human maintains; anything not explicitly listed is rejected, and a missing file fails **closed** — nothing is authorized by default. Every check, allowed or denied, is appended to an audit log.
- The whole thing runs on a **small, purpose-built agent framework** (`core/`, `context/`) rather than a heavyweight commercial one — see [`docs/DESIGN.md`](docs/DESIGN.md) for the reasoning, PEAS task-environment breakdown, and the context-engineering/memory-system design notes behind it.

## Architecture

```mermaid
flowchart TB
    subgraph Orchestrator["PTES Orchestrator"]
        direction LR
        P1["Recon<br/>(Plan-and-Solve)"] --> P2["Threat Modeling"] --> P3["Vulnerability<br/>Analysis"] --> P4["Exploitation"] --> P5["Post-<br/>Exploitation"]
    end
    P2 -.->|"same instance,<br/>set_ptes_phase()"| React["PostReconReActAgent<br/>(ReAct loop)"]
    P3 -.-> React
    P4 -.-> React
    P5 -.-> React
    P1 --> Plan["PlanSolveAgent"]

    Plan --> Core
    React --> Core

    subgraph Core["Core Agent Layer"]
        direction LR
        LLM["LLM interface<br/>(core/llm.py)"]
        Ctx["Context Engineering<br/>Gather→Select→Structure→Compress"]
        Mem[("Memory System<br/>Working / Episodic /<br/>Semantic / Perceptual")]
        LLM --- Ctx --- Mem
    end

    Core --> Tools["Tool Registry<br/>(tools/builtin/*)"]
    Tools --> Guard{{"Scope Guard<br/>core/scope.py<br/>fail-closed, human-authored"}}
    Guard -->|authorized| RPC["Metasploit RPC Client<br/>(metasploit/*)"]
    Guard -.->|rejected| Audit[("logs/scope_audit.log")]
    RPC --> MSF[("msfrpcd")]
    MSF --> Target(["Target host(s)"])

    style Guard fill:#7a2020,color:#fff,stroke:#c0392b,stroke-width:2px
    style Mem fill:#1f3a5f,color:#fff
```

```
firstpentestAgent/
├── agent/          # PlanSolveAgent (recon) + PostReconReActAgent (threat modeling → post-exploitation)
├── core/           # Agent base class, LLM interface, message system, lifecycle, config, scope guard
├── context/        # ContextBuilder: Gather → Select → Structure → Compress
├── memory/         # 4-tier memory manager: extraction, maintenance, embedding, SQLite/Qdrant/Neo4j stores
├── metasploit/     # msfrpc client wrapper (core, console, modules, jobs, sessions)
├── tools/          # Tool base/registry/chain + built-in tools (nmap_scan, run_module, set_option, sessions, jobs, memory...)
├── docs/           # DESIGN.md, TESTING.md, STATE_MODEL.md, TOOL_INTERFACE.md, threat modeling & pentest framework notes
├── tests/          # unit (mocked) / integration (live RPC) / e2e (live RPC + live CVE lab)
└── examples/       # runnable scripts, e.g. examples/run_plan_solve_agent.py
```

> Full design rationale, trade-offs, and the memory-system deep dive: [`docs/DESIGN.md`](docs/DESIGN.md).

## Demo

Every transcript below is a real, unedited run captured against a live target — no mocked output.

### 1. Live exploit against a real CVE (CVE-2017-5638, the Equifax-breach Struts2 OGNL injection)

The end-to-end test drives the agent's own tool layer (`SetOptionTool` → `RunModuleTool`) against a live [vulhub](https://github.com/vulhub/vulhub) `struts2/s2-045` container through a real `msfrpcd`. It proves two things with a real target, not a mock: the scope guard genuinely blocks exploitation until the target is marked `allow_exploit: true`, and once authorized the exploit really dispatches over HTTP against the container.

```
$ pytest tests/e2e/test_struts2_exploit.py -v -m e2e

tests/e2e/test_struts2_exploit.py::test_exploit_blocked_when_target_not_authorized_for_exploit PASSED [ 50%]
tests/e2e/test_struts2_exploit.py::test_exploit_dispatched_against_real_vulnerable_target_when_authorized PASSED [100%]

========================= 2 passed, 1 warning in 3.60s =========================
```

### 2. The recon agent, live LLM calls, live target — from natural-language goal to a structured asset inventory

`PlanSolveAgent` given nothing but a goal ("scan 127.0.0.1, identify web services and versions") against the same live lab, with a real `claude-haiku-4-5` call driving the planner and every step. It plans 4 steps, scans, correctly reuses the `-sV` result from step 1 instead of re-scanning in step 2 (memory in action), recognizes step 3 is out of its tool set's reach rather than improvising, and emits a structured JSON asset inventory in step 4:

```
🤖 recon_plan_solve 开始处理问题: 对目标主机 127.0.0.1 进行服务扫描，识别 Web 服务及其版本信息...
--- 正在生成计划 ---
✅ 计划已生成:
  1. 探测目标主机 127.0.0.1 的常见 Web 服务端口（80、443、8080、8443 等）开放状态
  2. 对已确认开放的 Web 端口执行服务版本识别扫描
  3. 针对识别出的 Web 服务进行深度指纹识别
  4. 汇总所有发现，整理成结构化资产清单

--- 正在执行计划 ---
-> 执行步骤 1/4: 探测目标主机 127.0.0.1 的常见 Web 服务端口...
🔧 调用工具: nmap_scan({'options': '-p 80,443,8080,8443 -sV', 'target': '127.0.0.1'})
   -> [*] Nmap: PORT     STATE  SERVICE   VERSION
      [*] Nmap: 80/tcp   closed http
      [*] Nmap: 443/tcp  closed https
      [*] Nmap: 8080/tcp open   http      Jetty 9.2.11.v20150529
      [*] Nmap: 8443/tcp closed https-alt
🔧 调用工具: memory({'action': 'add', 'content': '127.0.0.1 Web 服务端口扫描结果：8080/tcp 开放，运行 Jetty 9.2.11.v20150529...'})
✅ 步骤 1 已完成 — 8080 开放，Jetty 9.2.11.v20150529

-> 执行步骤 2/4: 对已确认开放的 Web 端口执行服务版本识别扫描...
🔧 调用工具: memory({'action': 'search', 'query': '127.0.0.1 8080 Jetty 版本识别', ...})
   -> 🔍 找到 1 条相关记忆 [nmap_scan] ... (重要性: 0.60)
✅ 步骤 2 已完成 — 前一步的 -sV 结果已覆盖本步骤，跳过重复扫描以避免不必要的网络开销

-> 执行步骤 3/4: 针对识别出的 Web 服务进行深度指纹识别...
✅ 步骤 3 已完成，结果: ⚠️ 该步骤超出侦查阶段职责范围 — 当前工具集仅有 nmap_scan（网络层），
   深度指纹识别需要 HTTP 客户端工具，不在可用列表中；已将已获得的结果整理为清单供下一步使用

-> 执行步骤 4/4: 汇总所有发现，整理成结构化资产清单...
================= FINAL RESULT =================
| 主机        | 端口 | 协议 | 状态   | 服务 | 产品  | 版本              | 应用类型   |
|-------------|------|------|--------|------|-------|-------------------|-----------|
| 127.0.0.1   | 8080 | TCP  | open   | http | Jetty | 9.2.11.v20150529  | Web Server|
| 127.0.0.1   | 80   | TCP  | closed | -    | -     | -                 | -         |
| 127.0.0.1   | 443  | TCP  | closed | -    | -     | -                 | -         |
| 127.0.0.1   | 8443 | TCP  | closed | -    | -     | -                 | -         |

{
  "asset_inventory": {
    "hosts": [{
      "ip_address": "127.0.0.1", "status": "up",
      "open_ports": [{"port": 8080, "protocol": "tcp", "state": "open",
        "service": {"name": "http", "product": "Jetty",
                    "version": "9.2.11.v20150529", "confidence": "high"}}]
    }]
  }
}
```

**A run earlier the same session also caught the scope guard doing its job under a planner mistake**: it briefly passed the nmap target as `127.0.0.1:8080` instead of a bare host, the guard correctly rejected the malformed target (fail-closed — it isn't the exact authorized entry, so it isn't guessed at), and every one of the 4 plan steps downstream then correctly reported the broken dependency chain and returned an empty asset list — rather than quietly hallucinating scan results to keep the plan looking complete.

### 3. Unit test suite — 49 tests, zero network calls, sub-second

```
$ pytest -v

tests/tool_tests/test_scope_guard.py::test_missing_scope_file_fails_closed PASSED
tests/tool_tests/test_scope_guard.py::test_metasploit_range_syntax_is_rejected_fail_closed PASSED
tests/tool_tests/test_scope_guard.py::test_exploit_requires_allow_exploit_flag PASSED
tests/tool_tests/test_nmap_scan.py::test_blocked_by_scope_guard_before_touching_client PASSED
tests/tool_tests/test_run_module.py::test_run_module_mock_exploit_blocked_without_allow_exploit PASSED
[... 44 more ...]

================= 49 passed, 9 deselected, 1 warning in 0.10s ==================
```

See [`docs/TESTING.md`](docs/TESTING.md) for the full three-layer testing strategy (unit / integration / e2e) and how to reproduce every layer, including the live exploit above, yourself.

## Preparations

- Install Metasploit: https://docs.metasploit.com/docs/using-metasploit/getting-started/nightly-installers.html
- Start the RPC server (this doesn't persist across Metasploit restarts — a msfconsole plugin, not a daemon):

    ```
    load msgrpc ServerHost=127.0.0.1 ServerPort=Portnum User=username Pass=password SSL=false
    ```

- Copy `scope.example.json` → `scope.json` and list only targets you have explicit authorization to test. Anything not listed is rejected before any tool touches the network — this file is gitignored on purpose.
- Configure `.env`: `LLM_MODEL_ID` / `LLM_API_KEY` / `LLM_BASE_URL` and `MSF_RPC_HOST` / `MSF_RPC_PORT` / `MSF_RPC_USERNAME` / `MSF_RPC_PASSWORD`.
- Run the recon example: `python examples/run_plan_solve_agent.py <authorized target>`

## Safety

This agent executes real exploit modules against real hosts. The scope guard (`core/scope.py`) is the load-bearing safety mechanism — it is data (`scope.json`), not something the model can talk itself past, and it fails closed. Only ever point this at targets you are explicitly authorized to test (a lab you own, or an engagement with signed authorization). `logs/scope_audit.log` records every authorization decision made.

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — full design rationale: agent paradigm choice, PEAS task environment, memory system design, context engineering
- [`docs/TESTING.md`](docs/TESTING.md) — three-layer testing strategy and how to reproduce it
- [`docs/STATE_MODEL.md`](docs/STATE_MODEL.md) — runtime state the agent maintains
- [`docs/TOOL_INTERFACE.md`](docs/TOOL_INTERFACE.md) — tool interface design principles
- [`docs/pentest_framework.md`](docs/pentest_framework.md) / [`docs/threat_modeling.md`](docs/threat_modeling.md) / [`docs/network_reconnaissance.md`](docs/network_reconnaissance.md) — methodology notes (Cyber Kill Chain, OSSTMM, PTES, MITRE ATT&CK)
