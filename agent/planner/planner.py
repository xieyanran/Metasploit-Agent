# 根据
from agent.models import Task
from agent.planner.task_graph import TaskGraph
from agent.planner.workflow import EXPLOIT_WORKFLOW

class Planner:
    def __init__(self):
        self.graph = TaskGraph() # empty

    # 清空旧TaskGraph
    def build_plan(self):
        graph = TaskGraph()
        previous = None
        for idx, goal in enumerate(EXPLOIT_WORKFLOW):
            task = Task(
                id = idx,
                goal = goal,
                name = goal +"task",
                description = f"Workflow step: {goal}",
                dependencies=[] if previous is None else [previous],
            )
            self.graph.add_task(task)
            previous = idx
        return graph

    def next_task(self):
        ready = self.graph.get_ready_tasks()

        if ready:
            return ready[0]

        return None        
    