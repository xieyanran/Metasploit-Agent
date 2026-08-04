from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from enum import Enum

#  Target
#    ├── hosts
#    │      ├── Host
#    │      │      ├── Port
#    │      │      │      └── Service
#    │      │      │              └── Vulnerability
#    │      │      └── tags
#    │
#    ├── credentials
#    ├── sessions
#    ├── loot
#    └── tasks

# ============================================================
# Target
# ============================================================

@dataclass
class Target:
    """
    Represents a penetration testing target.
    """

    address: str
    hostname: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    hosts: list["Host"] = field(default_factory=list)
    credentials: list["Credential"] = field(default_factory=list)
    sessions: list["Session"] = field(default_factory=list)
    loot: list["Loot"] = field(default_factory=list)
    tasks: list["Task"] = field(default_factory=list)


# ============================================================
# Host
# ============================================================

@dataclass
class Host:
    """
    Represents a discovered host.
    """

    address: str
    hostname: str | None = None
    os: str | None = None
    alive: bool = False
    ports: list["Port"] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


# ============================================================
# Port
# ============================================================

@dataclass
class Port:
    """
    Represents a network port.
    """

    number: int
    protocol: str
    state: str
    service: "Service | None" = None


# ============================================================
# Service
# ============================================================

@dataclass
class Service:
    """
    Represents a network service.
    """

    name: str
    product: str | None = None
    version: str | None = None
    extrainfo: str | None = None
    cpe: str | None = None
    vulnerabilities: list["Vulnerability"] = field(default_factory=list)


# ============================================================
# Vulnerability
# ============================================================

@dataclass
class Vulnerability:
    """
    Represents a discovered vulnerability.
    """

    name: str
    severity: str | None = None
    description: str | None = None
    references: list[str] = field(default_factory=list)
    exploitable: bool = False


# ============================================================
# Credential
# ============================================================

@dataclass
class Credential:
    """
    Represents a discovered credential.
    """

    username: str
    password: str | None = None
    hash: str | None = None
    source: str | None = None
    host: str | None = None


# ============================================================
# Session
# ============================================================

@dataclass
class Session:
    """
    Represents an active session.
    """

    id: int
    type: str
    platform: str
    user: str | None = None
    tunnel_peer: str | None = None
    via_exploit: str | None = None
    host: str | None = None


# ============================================================
# Loot
# ============================================================

@dataclass
class Loot:
    """
    Represents collected files or sensitive information.
    """

    name: str
    path: str
    type: str
    description: str | None = None
    host: str | None = None


# ============================================================
# Task
# ============================================================
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
@dataclass
class Task:
    """
    Represents one executable task.
    """
    id: int
    goal: str
    name: str
    tool: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    dependencies: list[int] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    error: str | None = None


# ============================================================
# Command Result
# ============================================================

@dataclass
class CommandResult:
    """
    Represents the result of executing a shell command.
    """

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


# ============================================================
# Tool Result
# ============================================================

@dataclass
class ToolResult:
    """
    Represents the result returned by a tool.
    """

    tool: str
    success: bool
    output: Any
    message: str = ""