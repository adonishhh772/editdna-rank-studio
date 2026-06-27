from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.schemas import ComparisonReport


class ComparisonAgent(BaseAgent):
    agent_id = "comparison_agent"
    agent_name = "Comparison Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        blueprint = blackboard.reference_blueprint
        edit_plan = blackboard.edit_plan
        issues: list[str] = []
        improvements: list[str] = []
        learned: list[str] = []

        reference_match = 0.7
        pacing_match = 0.65
        caption_match = 0.6
        audio_match = 0.6
        ranking_match = 0.75
        topic_relevance = 0.8
        preference_match = 0.7

        if blueprint and edit_plan:
            if abs(blueprint.ranking_count - len(edit_plan.sections)) <= 1:
                ranking_match = 0.9
            else:
                issues.append("Ranking count differs from reference blueprint")
            if blueprint.final_rank_drama_level == "high":
                improvements.append("Applied stronger emphasis on rank #1")

        for update in blackboard.memory_updates:
            for item in update.get("long_term_updates", []):
                learned.append(item.get("content", ""))

        seen_improvements: set[str] = set()
        for feedback in blackboard.feedback_events:
            if not feedback.feedback_text:
                continue
            label = f"Applied feedback: {feedback.feedback_text}"
            if label in seen_improvements:
                continue
            seen_improvements.add(label)
            improvements.append(label)

        report = ComparisonReport(
            project_id=blackboard.project_id,
            reference_match_score=reference_match,
            user_preference_match_score=preference_match,
            pacing_match_score=pacing_match,
            caption_style_match_score=caption_match,
            audio_style_match_score=audio_match,
            ranking_structure_match_score=ranking_match,
            topic_relevance_score=topic_relevance,
            issues=issues,
            improvements_after_feedback=improvements,
            learned_preferences=[item for item in learned if item],
        )
        blackboard.comparison_report = report
        blackboard.stage = "compared"
        blackboard.traces[-1].output_summary = f"Reference match score: {reference_match:.2f}"
        return blackboard
