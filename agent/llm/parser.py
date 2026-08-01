"""
LLM output parser.
"""

from __future__ import annotations

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

        raise NotImplementedError