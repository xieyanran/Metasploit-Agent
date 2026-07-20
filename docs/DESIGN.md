# Metasploit Agent Design

## Overview

### Goal

> Build a naive Metasploit agent. To achieve the automated pentest goal.

---

## Scope

### In Scope

- ...
- ...
- ...

### Out of Scope

- ...
- ...
- ...

---

## User Input

Describe what the agent accepts as input.

Example:

- Target host
- Exploit objective
- Optional module name

---

## Expected Output

Describe what the agent should return.

Example:

- Selected module
- Execution status
- Session information
- Failure reason

---

# Capabilities

The agent currently supports:

- [ ] Search Metasploit modules
- [ ] Retrieve module information
- [ ] Configure module options
- [ ] Execute modules
- [ ] Read execution results
- [ ] List active sessions

---

# Available Tools

| Tool | Description |
|-------|-------------|
| search_module | Search modules by keyword |
| get_module_info | Retrieve module details |
| set_module_option | Configure module options |
| run_module | Execute a module |
| list_sessions | Retrieve active sessions |

---

# Agent State

The agent maintains the following runtime state.

| State | Description |
|--------|-------------|
| target | Current target host |
| module | Selected module |
| payload | Selected payload |
| options | Current module options |
| execution_result | Latest execution result |
| session | Current session information |

---

# Reasoning Loop

```text
Receive Goal
      │
      ▼
Observe Current State
      │
      ▼
Reason
      │
      ▼
Select Tool
      │
      ▼
Execute Tool
      │
      ▼
Update State
      │
      ▼
Goal Completed?
      │
   Yes │ No
      ▼
    Finish
```

---

# Success Criteria

The first version is considered successful if it can:

- Search an exploit module
- Configure required options
- Execute the module
- Return the execution result
- Record the runtime state

---

# Future Work

- Automatic payload selection
- Session management
- Retry strategy
- Multi-step reasoning
- Planner Agent