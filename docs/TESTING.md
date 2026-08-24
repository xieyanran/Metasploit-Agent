# Testing Guide

> Status: Current (reflects the test suite as of the Engagement Scope Guard work)
>
> Purpose: explain what is tested, why it's structured this way, and how to reproduce every layer yourself — including the live exploitation run against a real CVE.

This project is tested in three layers of increasing cost and realism. The guiding rule: **the default `pytest` run must never touch the network, a real Metasploit instance, or a real target** — everything that does is opt-in via a marker.

| Layer | Command | Needs | Speed | Count |
|---|---|---|---|---|
| Unit (mock) | `pytest` | nothing | ~0.1s | 49 |
| Integration (live RPC) | `pytest -m integration` | a running `msfrpcd` | ~0.5s | 7 |
| End-to-end (live exploit) | `pytest -m e2e` | `msfrpcd` + the Struts2 lab (below) | ~3s | 2 |

Markers are registered in [`pytest.ini`](../pytest.ini); `addopts = -m "not integration and not e2e"` is what makes a bare `pytest` skip the two live layers automatically.

## Layer 1 — Unit tests (mocked, no external dependencies)

Every tool in `tools/builtin/` is tested against a fake `MetasploitClient` built with `unittest.mock.MagicMock` — no real `msfrpcd`, no network call, no target. This works cleanly because `MetasploitClient` (`metasploit/client.py`) is a thin facade: `client.modules` / `client.sessions` / `client.jobs` / `client.console` are independent sub-objects, so a test only needs to stub the one or two methods the tool under test actually calls.

```python
# tests/tool_tests/test_stop_job.py — the simplest example of the pattern
client = MagicMock()
client.jobs.stop.return_value = {"result": "success"}
tool = StopJobTool(client)

result = tool.execute(AgentState(), job_id=0)

assert result.success is True
client.jobs.stop.assert_called_once_with(0)
```

What each file covers:

| Tool | Test file | Notable cases |
|---|---|---|
| `nmap_scan` | `test_nmap_scan.py` | unsafe-char rejection, scope-guard rejection, console poll-until-not-busy, timeout |
| `run_module` | `test_run_module.py` | scope block, exploit-class gate (`allow_exploit`), successful dispatch |
| `set_option` | `test_set_option.py` | unknown-option rejection, scope block, option accumulation across calls, PAYLOAD/LHOST option merging |
| `search_module` / `get_module_info` / `show_option` | same-named files | thin pass-through to `client.modules.*`, argument shape |
| `list_sessions` / `execute_session` / `kill_meterpreter_session` / `stop_session` | same-named files | session-not-found, per-session-type branching (Meterpreter / shell / protocol-specific), `state.target.sessions` side effect |
| `compatible_payloads` / `shell_upgrade` / `session_compatible_modules` | same-named files | argument routing |
| `list_jobs` / `job_info` / `stop_job` | same-named files | pass-through |
| `core.scope.EngagementScope` | `test_scope_guard.py` | see below |

`memory_tool.py` and the empty `rag_tool.py` stub are intentionally **not** covered here — `memory_tool` doesn't take a `MetasploitClient` at all (it wraps `MemoryManager`, a different subsystem with its own I/O), and `rag_tool.py` is dead code not registered anywhere. Testing the memory subsystem is a separate follow-up, not part of this pass.

### Scope guard unit tests

`core/scope.py` implements the engagement-scope check described in [`DESIGN.md`](DESIGN.md): before any tool touches a real target, `EngagementScope.authorize()` decides whether it's allowed, entirely from a human-maintained `scope.json` — never from the model's own say-so. `tests/tool_tests/test_scope_guard.py` is pure unit testing against in-memory `EngagementScope` instances (no file I/O except where explicitly testing file loading), covering:

- single IP in scope → authorized; IP not listed → rejected with the target named in the reason
- CIDR containment (`192.168.56.0/24` covers `.50`; a `/32` entry does **not** cover a request for the whole `/24`)
- hostname glob entries (`*.lab.local`)
- Metasploit range syntax (`192.168.1.1-50`) is rejected outright — deliberately **not** parsed, fail-closed rather than guessed at
- exploit-class requests require `allow_exploit: true` on the matching entry; scan-class requests don't
- a missing `scope.json` produces an empty scope (fail-closed: everything rejected), not "allow by default"
- every `authorize()` call — allowed or rejected — appends a JSON-lines record to the audit log (verified against an isolated `tmp_path` log, not the real `logs/scope_audit.log`)

Run just this file:
```
pytest tests/tool_tests/test_scope_guard.py -v
```

## Layer 2 — Integration tests (live `msfrpcd`, no target required)

These call a real, running Metasploit RPC server — real msgpack over HTTP, real module database — but only for read-only or self-contained operations (module search/info/options, RPC login/logout). No exploit runs here.

Setup (see also the root [`README.md`](../README.md)):
```
msfrpcd -P 123456 -U msf -a 127.0.0.1 -p 55554 -S
```
Tests default to `host=127.0.0.1 port=55553 user=msf pass=123456` — match whatever you actually started, or edit the test.

Covered: `tests/rpc_test/test_login.py`, `tests/rpc_test/test_logout.py`, and the pre-existing live variants of `test_search_module.py` / `test_get_module_info.py` / `test_show_option.py` / `test_run_module.py` / `test_set_option.py` (each of those files has **both** a mock test that runs by default and a `@pytest.mark.integration` live test).

One real bug surfaced by actually writing `test_logout.py` properly: `MetasploitRPCClient.logout()` (`metasploit/rpc.py`) checks `self.logouttoken`, a field nothing in the class ever set — so `logout()` was a permanent no-op. Fixed by defaulting `logouttoken` to the caller's own token (self-logout) when not explicitly set.

Run:
```
pytest -m integration -v
```

## Layer 3 — End-to-end test against a real, live CVE

This is the layer that proves the agent's tool chain — not a mock, not a synthetic fixture — can really drive Metasploit against a real vulnerable service, and that the scope guard is a genuine technical control rather than a comment.

### The target: vulhub `struts2/s2-045` (CVE-2017-5638)

CVE-2017-5638 is the Apache Struts2 Jakarta Multipart parser OGNL injection — the vulnerability behind the 2017 Equifax breach. [vulhub](https://github.com/vulhub/vulhub) maintains a docker-compose reproduction using the real, unmodified, historically-vulnerable Struts2 build (not an artificially planted backdoor), which is why it was chosen over alternatives: it's a real CVE in real software, actively community-maintained, and Metasploit ships a mature module for it (`exploit/multi/http/struts2_content_type_ognl`).

### One-time setup

```bash
# 1. Container runtime (Colima: CLI-only, no Docker Desktop GUI needed)
brew install colima docker docker-compose
colima start --cpu 2 --memory 4 --disk 20

# 2. Pull just the one lab directory out of vulhub (not the whole monorepo)
mkdir -p lab
git clone --filter=blob:none --sparse --depth 1 https://github.com/vulhub/vulhub.git lab/vulhub
cd lab/vulhub && git sparse-checkout set struts2/s2-045

# 3. Bring the target up (bound to 127.0.0.1 only — see the edited port mapping
#    in lab/vulhub/struts2/s2-045/docker-compose.yml)
cd struts2/s2-045 && docker compose up -d
```

Verify it's up: `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/` should print `200`.

### Scope configuration

```bash
cp scope.example.json scope.json
```
and set the single entry's `target` to `127.0.0.1` with `allow_exploit: true` (see the checked-in `scope.example.json` for the exact shape). `scope.json` is gitignored — it's per-operator authorization data, not code.

### What the test actually does

`tests/e2e/test_struts2_exploit.py` drives the exploit through the agent's **own** tool layer — `SetOptionTool` then `RunModuleTool` — exactly as the agent itself would, not by talking to `msfrpcd` directly:

1. **`test_exploit_blocked_when_target_not_authorized_for_exploit`** — with `allow_exploit: false`, `set_option` succeeds (configuring a module is always allowed for an in-scope target) but `run_module` refuses to dispatch `exploit/multi/http/struts2_content_type_ognl` and returns a scope-guard rejection message. No RPC call to `modules.execute` is made.
2. **`test_exploit_dispatched_against_real_vulnerable_target_when_authorized`** — with `allow_exploit: true`, the same call path succeeds: `modules.execute` returns a real `job_id` from live `msfrpcd`, meaning Metasploit genuinely accepted and ran the module against `127.0.0.1:8080` — a network round trip against a real Java process, not a stub.

Run:
```
pytest tests/e2e/test_struts2_exploit.py -v -m e2e
```

### Why the assertion is "a job_id came back", not "here's a shell"

The payload used is `cmd/unix/generic` (a single command, no session, no listener needed — the simplest payload compatible with this exploit). That keeps the test deterministic and network-topology-independent: a session- or listener-based payload (e.g. a reverse Meterpreter) would need the container to open a connection back out through Colima's VM to a port on the Mac, which is unnecessary complexity for what this test needs to prove. `modules.execute` returning a `job_id` with no `RPCError` (contrast with the blocked case, where no RPC call happens at all) is the strongest signal obtainable through the RPC layer for this payload class.

For a more visceral, human-readable confirmation, this was also verified once by hand through `msfconsole`, driving the exact same module via `client.console` (the same primitive `nmap_scan.py` uses) instead of the job API:

```
msf exploit(multi/http/struts2_content_type_ognl) > check
[+] 127.0.0.1:8080 - The target is vulnerable. Successfully executed the injected code

msf exploit(multi/http/struts2_content_type_ognl) > exploit -z
[+] id
[*] Exploit completed, but no session was created.
```

`check` is Metasploit's own module code confirming it *actually ran attacker-controlled code* on the target (not just a version fingerprint match) — this is real code execution against a real, unpatched CVE, independent of anything this project's own wrapper code does. `cmd/unix/generic` doesn't relay the command's stdout back through the console for this module, which is why the automated test asserts on job dispatch rather than scraping console text for `uid=...`.

### Evidence this produces

Every scope decision made during the run — allowed or rejected — is appended to `logs/scope_audit.log` (gitignored, JSON Lines):
```json
{"timestamp": "...", "tool": "run_module", "target": "127.0.0.1", "require_exploit": true, "allowed": false, "reason": "target '127.0.0.1' is in scope for scanning but not authorized for exploit-class modules"}
{"timestamp": "...", "tool": "run_module", "target": "127.0.0.1", "require_exploit": true, "allowed": true, "reason": null}
```
That pair of lines — one real rejection, one real approval, against the same real target — is the concrete artifact worth keeping (screenshot, attach, or reference) as proof the guardrail is load-bearing and not decorative.

### Tearing down

```bash
cd lab/vulhub/struts2/s2-045 && docker compose down   # stop the target
colima stop                                            # stop the VM, free resources
```

## Security-specific test coverage

Beyond "does the tool work," a few tests exist specifically to validate the safety story, which matters more for a pentest agent than for typical application code:

- **Scope enforcement** — `test_scope_guard.py`, plus the blocked-path assertions inside `test_nmap_scan.py`, `test_run_module.py`, `test_set_option.py`, and the e2e test — all assert the *client is never called* (or the RPC call never fires) when a target is out of scope, not just that the returned `ToolResult.success` is `False`. That distinction matters: a check that fires the RPC call and only reports failure afterward isn't actually a guardrail.
- **Fail-closed defaults** — a missing `scope.json`, or an unparseable/ambiguous target expression (Metasploit range syntax), both resolve to *rejected*, never to *allowed*.
- **Exploit-class gating** — scan/auxiliary modules and exploit modules are checked against different authorization bits (general scope membership vs. `allow_exploit`), and both directions are tested (blocked without the flag, allowed with it) against both mocks and the real lab target.

## Known gaps / deliberately out of scope

- `memory/` subsystem (retrieval scoring, forgetting/consolidation) has no dedicated unit tests yet — it's pure logic and well-suited to the same mocking approach, just not part of this pass.
- No PTES "Reporting" stage exists yet (see `DESIGN.md`), so the e2e test proves exploitation, not report generation.
- Session-management tools (`execute_session`, `shell_upgrade`, `stop_session`, etc.) are only scope-checked indirectly, through the assumption that the session they operate on could only exist because `run_module` already passed the scope gate to create it. They don't re-validate scope themselves.
- Layer 1 (unit) runs automatically on every push/PR via [`.github/workflows/tests.yml`](../.github/workflows/tests.yml). Layers 2 and 3 still require a live `msfrpcd` and aren't wired into CI.
