from app.blackboard import ProjectBlackboard
from app.db import save_blackboard
from app.schemas import CandidateReviewStatusResponse, FeedbackEvent
from app.services.candidate_review_service import CandidateReviewService


class ApprovalService:
    def __init__(self) -> None:
        self.review_service = CandidateReviewService()

    def get_review_status(self, blackboard: ProjectBlackboard) -> CandidateReviewStatusResponse:
        return self.review_service.build_status(blackboard)

    async def start_candidate_review(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self.review_service.start_review(blackboard)

    async def approve_candidate(
        self,
        blackboard: ProjectBlackboard,
        candidate_id: str,
    ) -> ProjectBlackboard:
        return await self.review_service.approve_candidate(blackboard, candidate_id)

    async def reject_candidate(
        self,
        blackboard: ProjectBlackboard,
        candidate_id: str,
    ) -> ProjectBlackboard:
        return await self.review_service.reject_candidate(blackboard, candidate_id)

    async def skip_current_slot(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self.review_service.skip_current_slot(blackboard)

    async def reorder_candidates(
        self,
        blackboard: ProjectBlackboard,
        candidate_ids: list[str],
    ) -> ProjectBlackboard:
        lookup = {item.candidate_id: item for item in blackboard.approved_candidates}
        reordered = [lookup[candidate_id] for candidate_id in candidate_ids if candidate_id in lookup]
        for index, candidate in enumerate(reordered, start=1):
            candidate.recommended_rank = index
        blackboard.approved_candidates = reordered
        save_blackboard(blackboard)
        return blackboard

    async def record_feedback(
        self,
        blackboard: ProjectBlackboard,
        feedback: FeedbackEvent,
    ) -> ProjectBlackboard:
        blackboard.feedback_events.append(feedback)
        save_blackboard(blackboard)
        return blackboard
