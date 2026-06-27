from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.constants.video_sources import is_platform_video_url
from app.schemas import CandidateVideo


class RankingAgent(BaseAgent):
    agent_id = "ranking_agent"
    agent_name = "Ranking Agent"

    def _compute_score(self, candidate: CandidateVideo, memory_context: dict) -> float:
        score = (
            0.30 * candidate.topic_match_score
            + 0.20 * candidate.visual_quality_score
            + 0.15 * candidate.reference_style_fit_score
            + 0.10 * candidate.motion_energy_score
            + 0.10 * candidate.text_relevance_score
            + 0.10 * candidate.source_safety_score
            + 0.05 * candidate.audio_quality_score
        )
        memory_text = str(memory_context.get("final_answer", "")).lower()
        reason_lower = candidate.reason.lower()
        if "demo" in memory_text and ("demo" in reason_lower or candidate.visual_quality_score > 0.6):
            score += 0.08
        if "abstract" in memory_text and "reject" in memory_text and "abstract" in reason_lower:
            score -= 0.15
        if "dramatic" in memory_text and candidate.motion_energy_score > 0.7:
            score += 0.05
        return min(max(score, 0.0), 1.0)

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        ranking_count = blackboard.reference_blueprint.ranking_count if blackboard.reference_blueprint else 5
        usable = [
            candidate
            for candidate in blackboard.candidate_pool
            if candidate.local_file_path
            or (candidate.source_url and is_platform_video_url(candidate.source_url))
        ]
        if not usable:
            usable = blackboard.candidate_pool

        for candidate in usable:
            candidate.overall_score = self._compute_score(candidate, blackboard.memory_context)

        ranked = sorted(usable, key=lambda item: item.overall_score, reverse=True)[:ranking_count]
        for index, candidate in enumerate(ranked, start=1):
            candidate.recommended_rank = index
            candidate.status = "selected"

        blackboard.selected_candidates = ranked
        blackboard.stage = "ranking_selected"
        blackboard.traces[-1].output_summary = f"Selected top {len(ranked)} candidates"
        return blackboard
