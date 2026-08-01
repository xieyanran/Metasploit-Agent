"""
LLM response.
"""

from __future__ import annotations
from dataclasses import dataclass

@dataclass
class LLMResponse:
    """
    Response returned by an LLM.
    """

    content: str
    finish_reason: str | None = None
    model: str | None = None
    usage: dict | None = None