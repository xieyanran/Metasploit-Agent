"""
OpenAI implementation.
"""
from __future__ import annotations
from agent.llm.base import BaseLLM
from agent.llm.message import Message
from agent.llm.response import LLMResponse
from openai import OpenAI

class OpenAILLM(BaseLLM):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.5",
    ):
        self.model = model
        self.client = OpenAI(api_key = api_key)

    def generate(self, 
                 messages: list[Message],
                 ) -> LLMResponse:

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": m.role,
                    "content": m.content,
                }
                for m in messages
            ],
        )

        return LLMResponse(
            content = response.choices[0].message.content,
            finish_reason = response.choices[0].finish_reason,
            model = response.model,
            usage = response.usage.model_dump(),
        )

