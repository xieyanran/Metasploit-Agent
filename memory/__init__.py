"""HelloAgents记忆系统模块

按照第8章架构设计的分层记忆系统：
- Memory Core Layer: 记忆核心层
- Memory Types Layer: 记忆类型层
- Storage Layer: 存储层
- Integration Layer: 集成层

Reference: https://github.com/jjyaoao/HelloAgents/tree/learn_version/hello_agents/memory
（整个 memory/ 目录为该仓库的逐文件移植，供本项目的 tools/builtin/memory_tool.py 使用）
"""

# Memory Core Layer (记忆核心层)
from .manager import MemoryManager

# Memory Types Layer (记忆类型层)
from .types.working import WorkingMemory
from .types.episodic import EpisodicMemory
from .types.semantic import SemanticMemory
from .types.perceptual import PerceptualMemory

# Storage Layer (存储层)
from .storage.document_store import DocumentStore, SQLiteDocumentStore

# Base classes and utilities
from .base import MemoryItem, MemoryConfig, BaseMemory
from .enums import Outcome

__all__ = [
    # Core Layer
    "MemoryManager",

    # Memory Types
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "PerceptualMemory",

    # Storage Layer
    "DocumentStore",
    "SQLiteDocumentStore",

    # Base
    "MemoryItem",
    "MemoryConfig",
    "BaseMemory",
    "Outcome",
]
