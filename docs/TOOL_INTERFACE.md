# Tool Interface Specification

> Version: 0.1.0
>
> Status: Draft
>
> Purpose: Define the tool interface exposed to the LLM. This document specifies what the agent can do, independent of the underlying Metasploit implementation.

---

# Design Principles

Every tool should follow these principles:

- Single Responsibility
- Stateless Interface
- Deterministic Output
- Structured Response
- LLM-friendly Description

---

# Tool Categories

The current version contains two categories of tools.

| Category | Description |
|----------|-------------|
| Observation | Retrieve information without changing the environment |
| Action | Perform operations that modify the environment |

---

# Tool List

## Observation Tools

### search_module

**Description**

Search Metasploit modules using a keyword.

**Input**

| Parameter | Type | Required | Description |
|----------|------|----------|-------------|
| keyword | string | Yes | Search keyword |

**Output**

Returns a list of matching modules.

---

### get_module_info

**Description**

Retrieve detailed information for a module.

**Input**

| Parameter | Type | Required |
|----------|------|----------|
| module_name | string | Yes |

**Output**

Returns:

- module type
- description
- rank
- references
- required options
- supported payloads

---

### list_sessions

**Description**

Retrieve all active sessions.

**Input**

None

**Output**

Returns all current Meterpreter/Shell sessions.

---

## Action Tools

### set_module_options

**Description**

Configure module options before execution.

**Input**

| Parameter | Type | Required |
|----------|------|----------|
| module_name | string | Yes |
| options | object | Yes |

Example:

```json
{
  "RHOSTS": "192.168.1.10",
  "RPORT": 445
}
```

**Output**

Returns whether the configuration succeeded.

---

### execute_module

**Description**

Execute a Metasploit module.

**Input**

| Parameter | Type | Required |
|----------|------|----------|
| module_name | string | Yes |

**Output**

Returns execution status and job information.

---

# Unified Response Format

All tools must return the same response structure.

```json
{
  "success": true,
  "message": "Human readable message",
  "data": {}
}
```

Where:

| Field | Description |
|-------|-------------|
| success | Whether the tool executed successfully |
| message | Short explanation |
| data | Structured result |

---

# Error Handling

Every tool should report errors using the same format.

Example:

```json
{
  "success": false,
  "message": "Module not found",
  "data": null
}
```

Common error types include:

- Invalid parameters
- Module not found
- Missing required options
- RPC connection failure
- Execution timeout

---

# Tool Constraints

Current limitations:

- Supports one module execution at a time
- Does not automatically select payloads
- Does not retry failed executions
- Does not perform automatic reconnaissance
- Does not manage multiple concurrent sessions

---

# Future Tools

The following tools are planned but not implemented.

## Module

- search_payload
- check_module
- list_payloads

## Session

- interact_session
- stop_session
- upgrade_session

## Job

- list_jobs
- stop_job

## Workspace

- create_workspace
- switch_workspace

---

# Naming Convention

All tool names should follow:

<verb>_<object>

Examples:

- search_module
- get_module_info
- execute_module
- list_sessions

Avoid:

- exploit()
- attack()
- run()

because they are ambiguous.

---

# Version History

| Version | Changes |
|----------|---------|
| 0.1.0 | Initial draft |