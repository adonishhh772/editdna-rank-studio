from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard


class HumanGateAgent(BaseAgent):
    agent_id = "human_gate"
    agent_name = "Human Gate Agent"

    def __init__(self, gate_type: str) -> None:
        self.gate_type = gate_type

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        blackboard.waiting_for_human = True
        blackboard.human_gate_type = self.gate_type
        blackboard.stage = f"waiting_{self.gate_type}"
        blackboard.traces[-1].status = "waiting_for_human"
        blackboard.traces[-1].output_summary = f"Awaiting human approval: {self.gate_type}"
        return blackboard
