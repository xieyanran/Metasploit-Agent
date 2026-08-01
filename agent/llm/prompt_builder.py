"""
Prompt Builder.
"""
from __future__ import annotations
from agent.llm.message import Message
from agent.state import Observation

class PromptBuilder:
    def build(
        self,
        observation: Observation,
    ) -> list[Message]:

        # system: model role
        system = Message(
            role = "system",
            content=(
                "You are a professional penetration tester."
            ),
        )

        # developer: 遵守哪些规则

        # user: currently environment
        user = Message(
            role = "user",
            content = str(observation)
        )

        return [
            system,
            user,
        ]
