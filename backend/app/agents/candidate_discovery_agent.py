from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.services.candidate_review_service import CandidateReviewService


class CandidateDiscoveryAgent(BaseAgent):
    agent_id = "candidate_discovery"
    agent_name = "Candidate Discovery"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.topic_research:
            raise RuntimeError("Topic research is required")

        review_service = CandidateReviewService()
        blackboard.candidate_pool = []
        blackboard.selected_candidates = []
        blackboard.approved_candidates = []
        blackboard.rejected_candidates = []
        blackboard = review_service.initialize_queue(blackboard)

        topic = blackboard.topic or ""
        slot_count = len(blackboard.candidate_review_queue)
        blackboard.stage = "concepts_discovered"
        trace = self.active_trace(blackboard)
        trace.input_summary = f"Topic: {topic[:80]}"
        trace.output_summary = f"Prepared {slot_count} concepts for sequential review"
        trace.visible_reasoning = (
            "Concepts ready. Each slot will search, download, analyse, then wait for your approval."
        )
        return blackboard
