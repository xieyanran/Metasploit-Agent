# State Model

> Version: 0.1.0
>
> Status: Draft
>
> Purpose: Define the runtime state maintained by the Metasploit Agent. The state represents the agent's current understanding of the task and is continuously updated throughout execution.

---

# Overview

The Agent maintains a runtime state during execution.

The state serves as the single source of truth for:

- Current objective
- Current execution context
- Tool outputs
- Execution history
- Final result

The LLM should reason based on the current state instead of relying solely on conversation history.

---

# State Structure

The runtime state consists of the following components.

| State | Description |
|--------|-------------|
| Goal | User's objective |
| Target | Target information |
| Module | Selected Metasploit module |
| Payload | Selected payload |
| Options | Module configuration |
| Execution | Latest execution result |
| Sessions | Active sessions |
| History | Previous tool calls |
| Status | Current agent status |

---

# Goal State

Represents the task assigned to the agent.

| Field | Description |
|--------|-------------|
| objective | High-level objective |
| constraints | Optional execution constraints |
| completed | Whether the goal has been achieved |

Example:

```text
Objective:
Exploit FTP service on target host.
```

---

# Target State

Represents information about the target.

| Field | Description |
|--------|-------------|
| host | Target IP or hostname |
| port | Target port |
| service | Service name |
| version | Service version |

Example:

```text
Host: 192.168.1.20
Port: 21
Service: FTP
Version: vsftpd 2.3.4
```

---

# Module State

Represents the currently selected Metasploit module.

| Field | Description |
|--------|-------------|
| name | Module name |
| type | exploit / auxiliary / post |
| rank | Module reliability |
| loaded | Whether the module is loaded |

Example:

```text
exploit/unix/ftp/vsftpd_234_backdoor
```

---

# Payload State

Represents the payload selected for execution.

| Field | Description |
|--------|-------------|
| name | Payload name |
| configured | Whether payload options are configured |

---

# Module Options State

Represents all module parameters.

Example:

| Option | Value |
|---------|------|
| RHOSTS | 192.168.1.20 |
| RPORT | 21 |
| LHOST | 192.168.1.5 |

The agent should always treat this as the current configuration.

---

# Execution State

Represents the latest module execution.

| Field | Description |
|--------|-------------|
| started | Execution started |
| finished | Execution finished |
| success | Whether execution succeeded |
| job_id | Metasploit job ID |
| message | Execution summary |

---

# Session State

Represents all active sessions.

Each session should contain:

| Field | Description |
|--------|-------------|
| session_id | Session identifier |
| type | shell / meterpreter |
| target | Connected host |
| status | Active / Closed |

---

# Tool History

Stores previous tool invocations.

Each record should contain:

- Tool name
- Input
- Output
- Timestamp

Purpose:

- Avoid repeated tool calls
- Support reasoning
- Improve explainability

Example:

```text
search_module("vsftpd")

↓

Found:
exploit/unix/ftp/vsftpd_234_backdoor
```

---

# Agent Status

Represents the current lifecycle stage.

Possible values:

- Idle
- Planning
- Observing
- Executing
- Waiting
- Completed
- Failed

Only one status should be active at any time.

---

# State Lifecycle

```text
Receive Goal
      │
      ▼
Initialize State
      │
      ▼
Update Target
      │
      ▼
Select Module
      │
      ▼
Configure Options
      │
      ▼
Execute Module
      │
      ▼
Update Session
      │
      ▼
Goal Completed
```

---

# Design Principles

The runtime state should satisfy the following principles:

- Single Source of Truth
- Explicit State Transitions
- Immutable History
- Structured Data
- Serializable
- LLM-readable

---

# Future Extensions

The following state objects may be added in future versions.

## Workspace

Maintain multiple Metasploit workspaces.

---

## Knowledge

Store learned information during execution.

---

## Memory

Persist information across multiple tasks.

---

## Planner

Store intermediate reasoning plans.

---

## Report

Collect evidence for automatic report generation.

---

# Version History

| Version | Changes |
|----------|---------|
| 0.1.0 | Initial draft |