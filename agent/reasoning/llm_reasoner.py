from agent.reasoning.reasoner import Reasoner
from agent.llm.prompt_builder import PromptBuilder
from agent.reasoning.observer import Observation
from agent.llm.openai_llm import OpenAILLM
from agent.llm.parser import OutputParser
from agent.llm.message import Message
from agent.state import Decision

class LLMReasoner(Reasoner):
    def __init__(self, llm: OpenAILLM, prompt_builder: PromptBuilder, parser: OutputParser):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.parser = parser

    def think(self, observation: Observation) -> Decision:

        messages = self.prompt_builder.build(observation)

        response = self.llm.generate(messages)

        decision = self.parser.parse(response.content)

        return decision


        

