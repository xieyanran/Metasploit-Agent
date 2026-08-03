"""
LLM output parser.
"""

from __future__ import annotations
import json
import re
from agent.state import Decision

class OutputParser:

    def parse(
        self,
        text: str,
    ) -> Decision:

        #
        # JSON Parsing
        # Function Calling
        # Structured Output
        #

        text = text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()

        
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse LLM output as JSON:\n{text}"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError("LLM output must be a JSON object.")

        tool = data.get("tool")

        parameters = data.get("parameters", {})

        finish = data.get("finish", False)

        reasoning = data.get("reasoning", "")

        if tool is not None and not isinstance(tool, str):
            raise ValueError("'tool' must be a string.")

        if not isinstance(parameters, dict):
            raise ValueError("'parameters' must be a dictionary.")

        if not isinstance(finish, bool):
            raise ValueError("'finish' must be a boolean.")

        if not isinstance(reasoning, str):
            raise ValueError("'reasoning' must be a string.")

        return Decision(
            tool=tool,
            parameters=parameters,
            finish=finish,
            reasoning=reasoning,
        )