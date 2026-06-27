from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard


class TopicAgent(BaseAgent):
    agent_id = "topic_agent"
    agent_name = "Topic Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.topic:
            raise RuntimeError("Topic is required")
        blackboard.stage = "topic_set"
        blackboard.traces[-1].output_summary = f"Topic set: {blackboard.topic}"
        return blackboard
