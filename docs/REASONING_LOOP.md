# Reasoning Loop

> Version: 0.1.0
>
> Status: Draft
>
> Purpose: Define the decision-making workflow of the Metasploit Agent. This document describes how the agent observes the environment, reasons about the current state, selects tools, and updates its state until the task is completed.

---

# Overview

The Metasploit Agent operates as a continuous reasoning loop.

Instead of executing a fixed sequence of commands, the agent repeatedly:

1. Observe
2. Reason
3. Decide
4. Execute
5. Update
6. Repeat

This loop continues until the objective has been achieved or the task is terminated.

---

# Reasoning Cycle

```text
                ┌─────────────────────┐
                │    Receive Goal     │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Initialize State    │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Observe Current     │
                │ Runtime State       │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │    Reason About     │
                │   Current Situation │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │    Select Next Tool │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │    Execute Tool     │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │   Update State      │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Goal Completed ?    │
                └──────┬────────┬─────┘
                       │Yes     │No
                       ▼        │
                 ┌──────────┐   │
                 │ Finish   │◄──┘
                 └──────────┘
```

---

# Phase 1 — Receive Goal

The agent receives an execution objective from the user.

Example:

- Search for a suitable exploit
- Exploit a target host
- Check whether a vulnerability is exploitable

The goal is stored in the runtime state.

---

# Phase 2 — Initialize State

The agent creates an empty runtime state.

This includes:

- Goal
- Target
- Module
- Payload
- Tool History
- Sessions
- Execution Status

---

# Phase 3 — Observe

The agent inspects the current runtime state.

Typical questions include:

- What information is already available?
- What information is missing?
- Has a module already been selected?
- Have we already executed a tool?
- Are there any active sessions?

No external actions are performed during this phase.

---

# Phase 4 — Reason

Based on the current state, the agent determines what should happen next.

Examples:

- Search for a module
- Retrieve module details
- Configure module options
- Execute the exploit
- Retrieve session information
- Finish execution

Reasoning should always depend on the current runtime state rather than conversation history alone.

---

# Phase 5 — Select Tool

The agent chooses exactly one tool.

Examples:

- search_module
- get_module_info
- set_module_options
- execute_module
- list_sessions

The selected tool should directly contribute to the current objective.

---

# Phase 6 — Execute Tool

The selected tool is executed.

Execution returns:

- Success or failure
- Structured output
- Error information
- Additional observations

The reasoning engine should never assume the execution succeeded.

---

# Phase 7 — Update State

The runtime state is updated using the tool output.

Possible updates include:

- Module selected
- Options configured
- Execution result stored
- Session created
- History appended

The updated state becomes the input for the next reasoning cycle.

---

# Phase 8 — Goal Evaluation

The agent evaluates whether the objective has been achieved.

Possible outcomes:

- Completed
- Continue
- Failed

If not completed, another reasoning cycle begins.

---

# State Transition

```text
Current State
      │
      ▼
Reason
      │
      ▼
Tool Selection
      │
      ▼
Tool Execution
      │
      ▼
State Update
      │
      ▼
Next State
```

Every reasoning cycle produces a new runtime state.

---

# Failure Handling

If a tool execution fails, the agent should:

1. Record the failure
2. Update execution history
3. Decide whether recovery is possible
4. Continue or terminate

Failures should never be silently ignored.

---

# Design Principles

The reasoning loop follows these principles:

- Observe before acting
- One decision per iteration
- One tool execution per iteration
- State-driven reasoning
- Explicit state transitions
- Recoverable failures
- Explainable decisions

---

# Termination Conditions

The reasoning loop ends when one of the following conditions is met:

- Goal completed
- User terminates execution
- Fatal execution error
- Maximum iteration limit reached

---

# Future Improvements

Future versions may introduce:

- Multi-tool planning
- Tool retry strategies
- Reflection after failure
- Confidence scoring
- Parallel tool execution
- Multi-agent collaboration

---

# Version History

| Version | Changes |
|---------|---------|
| 0.1.0 | Initial draft |