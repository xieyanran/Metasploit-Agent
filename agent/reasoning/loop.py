# Observe -> Think -> Act -> Repeat
"""
Reasoning Loop
"""
from agent.reasoning.observer import Observer
from agent.reasoning.reasoner import Reasoner
from agent.state import AgentState, ToolResult
from agent.reasoning.action import ActionExecutor

class ReasoningLoop:
    def __init__(
            self,
            observer: Observer,
            reasoner: Reasoner,
            executor: ActionExecutor,
        ):
        self.observer = observer
        self.reasoner = reasoner
        self.executor = executor

    def step(self, state: AgentState) -> ToolResult:
        """
        Execute one reasoning step.
        """
        observation = self.observer.observe(state)
        decision = self.reasoner.think(observation)
        result = self.executor.execute(decision=decision, state=state)
        
        return result
    
    def run(self, state: AgentState) -> ToolResult:
        """
        Run until the current task is completed.
        """
        results: list[ToolResult] = []

        while True:
            observation = self.observer.observe(state)
            decision = self.reasoner.think(observation)
            if decision.finish:
                break
            result = self.executor.execute(decision=decision, state=state)
            results.append(result)

        return results


