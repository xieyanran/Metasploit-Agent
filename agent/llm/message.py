"""
LLM message.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class Message:
    """
    Chat message.
    """
    role: str
    content: str