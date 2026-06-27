from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.schemas import CandidateVideo


class CandidateAnalysisSwarmAgent(BaseAgent):
    agent_id = "candidate_analysis_swarm"
    agent_name = "Candidate Analysis Swarm"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        from app.agents.candidate_segment_agent import CandidatePreviewAgent, CandidateSegmentAgent
        from app.agents.candidate_visual_analysis_agent import CandidateVisualAnalysisAgent

        if "_candidate_analysis_request" not in blackboard.memory_context:
            raise RuntimeError("Candidate analysis request is missing")

        parent_trace = self.active_trace(blackboard)
        parent_agent_id = self.agent_id
        request = blackboard.memory_context["_candidate_analysis_request"]
        concept = request.get("concept", "clip") if isinstance(request, dict) else "clip"

        visual_agent = CandidateVisualAnalysisAgent()
        segment_agent = CandidateSegmentAgent()
        preview_agent = CandidatePreviewAgent()

        blackboard = await visual_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )
        blackboard = await segment_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )
        blackboard = await preview_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )

        parent_trace.input_summary = f"Analysis swarm for '{concept}'"
        parent_trace.output_summary = "Visual, segment, and preview passes complete"
        parent_trace.visible_reasoning = (
            "Swarm analysed topic/visual fit, selected stitch highlight, and generated preview."
        )
        parent_trace.metadata["sub_agents"] = [
            CandidateVisualAnalysisAgent.agent_id,
            CandidateSegmentAgent.agent_id,
            CandidatePreviewAgent.agent_id,
        ]
        parent_trace.metadata["swarm"] = True
        return blackboard


async def analyze_candidate_with_swarm(
    blackboard: ProjectBlackboard,
    candidate: CandidateVideo,
) -> tuple[ProjectBlackboard, CandidateVideo]:
    blackboard.memory_context["_candidate_analysis_request"] = candidate.model_dump()
    swarm = CandidateAnalysisSwarmAgent()
    blackboard = await swarm.execute(blackboard, swarm=True)
    result_raw = blackboard.memory_context.pop("_candidate_analysis_result", None)
    blackboard.memory_context.pop("_candidate_analysis_request", None)
    if not result_raw:
        raise RuntimeError("Candidate analysis swarm produced no result")
    return blackboard, CandidateVideo.model_validate(result_raw)
