# Reasoner 不直接调用 LLM，而应该作为一个统一的推理接口
"""
Base Reasoner interface.
"""
from __future__ import annotations
from agent.reasoning.observer import Observation
from agent.state import Decision
from abc import ABC, abstractmethod

class Reasoner(ABC):
    """
    Base class for all reasoning engines.
    A Reasoner decides what to do next based on the current observation.
    """

    @abstractmethod
    def think(self, observation: Observation) -> Decision:
        raise NotImplementedError
