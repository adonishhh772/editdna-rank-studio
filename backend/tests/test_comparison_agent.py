import pytest

from app.agents.comparison_agent import ComparisonAgent
from app.blackboard import ProjectBlackboard
from app.schemas import AgentTrace, FeedbackEvent


@pytest.mark.asyncio
async def test_comparison_agent_deduplicates_repeated_feedback_improvements() -> None:
    blackboard = ProjectBlackboard(
        project_id="proj-compare",
        run_id="run-compare",
        user_id="default-user",
        feedback_events=[
            FeedbackEvent(
                feedback_id="fb-1",
                project_id="proj-compare",
                run_id="run-compare",
                user_id="default-user",
                feedback_type="final_approve",
                feedback_text="Final approve",
            ),
            FeedbackEvent(
                feedback_id="fb-2",
                project_id="proj-compare",
                run_id="run-compare",
                user_id="default-user",
                feedback_type="final_approve",
                feedback_text="Final approve",
            ),
        ],
        traces=[
            AgentTrace(
                trace_id="trace-1",
                project_id="proj-compare",
                run_id="run-compare",
                agent_id="comparison_agent",
                agent_name="Comparison Agent",
                status="running",
            )
        ],
    )

    result = await ComparisonAgent().run(blackboard)

    assert result.comparison_report is not None
    assert result.comparison_report.improvements_after_feedback == ["Applied feedback: Final approve"]
