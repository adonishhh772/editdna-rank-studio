from app.agents.base import BaseAgent
from app.agents.moe_bus import MoEBus
from app.agents.story_agent import CaptionAgent, CutAgent, MotionAgent, StoryAgent
from app.blackboard import ProjectBlackboard


class MoEEditSwarmAgent(BaseAgent):
    agent_id = "moe_edit_swarm"
    agent_name = "MoE Edit Swarm"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        experts = [StoryAgent(), CutAgent(), CaptionAgent(), MotionAgent()]
        moe_bus = MoEBus()
        blackboard = await moe_bus.run_moe_pipeline(experts, blackboard)

        parent_trace = self.active_trace(blackboard)
        routing = blackboard.moe_routing
        parent_trace.input_summary = "Running Story, Cut, Caption, and Motion experts in parallel"
        parent_trace.output_summary = f"{len(blackboard.expert_proposals)} expert proposals collected"
        parent_trace.visible_reasoning = (
            routing.reasoning if routing and routing.reasoning else "MoE experts proposed edit changes"
        )
        parent_trace.metadata["sub_agents"] = [expert.agent_id for expert in experts]
        parent_trace.metadata["swarm"] = True
        parent_trace.metadata["agent_messages"] = len(blackboard.agent_messages)
        return blackboard
