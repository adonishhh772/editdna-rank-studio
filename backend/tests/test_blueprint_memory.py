from unittest.mock import AsyncMock, patch

import pytest

from app.agents.mubit_memory_agent import MubitMemoryAgent, ReferenceBlueprintMemoryAgent
from app.blackboard import ProjectBlackboard
from app.schemas import AgentTrace, FeedbackEvent, ReferenceBlueprint
from app.services.blueprint_memory import build_reference_blueprint_memory_content


def _sample_blueprint(project_id: str) -> ReferenceBlueprint:
    return ReferenceBlueprint(
        blueprint_id="bp-1",
        project_id=project_id,
        video_type="ranking_video",
        aspect_ratio="9:16",
        duration_sec=30.0,
        ranking_count=5,
        ranking_order="5_to_1",
        hook_duration_sec=3.0,
        average_item_duration_sec=4.0,
        outro_duration_sec=2.0,
        section_order=[],
        caption_style={"prominence": "high", "case": "upper"},
        text_overlay_style={},
        transition_style={},
        audio_style={"mood": "energetic"},
        motion_style={"energy": "high"},
        pacing_style={"tempo": "fast"},
        hook_style="countdown",
        rank_reveal_style="dramatic",
        final_rank_drama_level="high",
        confidence=0.9,
    )


def test_build_reference_blueprint_memory_content_includes_key_traits() -> None:
    content = build_reference_blueprint_memory_content(_sample_blueprint("proj-1"))

    assert "5 ranks" in content
    assert "countdown" in content
    assert "dramatic" in content
    assert "fast" in content


@pytest.mark.asyncio
async def test_write_reference_blueprint_memory_stores_updates() -> None:
    blackboard = ProjectBlackboard(
        project_id="proj-real",
        run_id="run-real",
        user_id="default-user",
        reference_blueprint=_sample_blueprint("proj-real"),
    )

    with patch("app.agents.mubit_memory_agent.MubitMemoryClient") as client_cls:
        client = client_cls.return_value
        client.remember_episodic = AsyncMock(return_value={"job_id": None})
        client.remember_long_term = AsyncMock(return_value={"job_id": None})

        result = await MubitMemoryAgent().write_reference_blueprint_memory(blackboard)

    assert len(result.memory_updates) == 1
    update = result.memory_updates[0]
    assert update["episodic_updates"]
    assert update["long_term_updates"]
    assert "reference blueprint" in update["summary"].lower()
    client.remember_episodic.assert_awaited_once()
    client.remember_long_term.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_reference_blueprint_memory_stores_updates_when_mubit_fails() -> None:
    blackboard = ProjectBlackboard(
        project_id="proj-fallback",
        run_id="run-fallback",
        user_id="default-user",
        reference_blueprint=_sample_blueprint("proj-fallback"),
    )

    with patch("app.agents.mubit_memory_agent.MubitMemoryClient") as client_cls:
        client = client_cls.return_value
        client.remember_episodic = AsyncMock(side_effect=RuntimeError("Mubit unavailable"))
        client.remember_long_term = AsyncMock(return_value={"job_id": None})

        result = await MubitMemoryAgent().write_reference_blueprint_memory(blackboard)

    assert len(result.memory_updates) == 1
    update = result.memory_updates[0]
    assert update["episodic_updates"]
    assert update["long_term_updates"]
    client.remember_episodic.assert_awaited_once()
    client.remember_long_term.assert_not_awaited()


@pytest.mark.asyncio
async def test_reference_blueprint_memory_agent_writes_trace_and_updates() -> None:
    blackboard = ProjectBlackboard(
        project_id="proj-swarm",
        run_id="run-swarm",
        user_id="default-user",
        reference_blueprint=_sample_blueprint("proj-swarm"),
    )

    with patch("app.agents.mubit_memory_agent.MubitMemoryClient") as client_cls:
        client = client_cls.return_value
        client.remember_episodic = AsyncMock(return_value={"job_id": None})
        client.remember_long_term = AsyncMock(return_value={"job_id": None})

        result = await ReferenceBlueprintMemoryAgent().execute(
            blackboard,
            parent_agent_id="reference_analyst",
            swarm=True,
        )

    memory_trace = result.traces[-1]
    assert memory_trace.agent_id == "reference_blueprint_memory"
    assert memory_trace.status == "complete"
    assert memory_trace.metadata["parent_agent_id"] == "reference_analyst"
    assert "reference blueprint" in memory_trace.output_summary.lower()
    assert len(result.memory_updates) == 1


@pytest.mark.asyncio
async def test_write_feedback_memory_stores_updates_when_mubit_fails() -> None:
    blackboard = ProjectBlackboard(
        project_id="proj-feedback",
        run_id="run-feedback",
        user_id="default-user",
        feedback_events=[
            FeedbackEvent(
                feedback_id="fb-1",
                project_id="proj-feedback",
                run_id="run-feedback",
                user_id="default-user",
                feedback_type="final_approve",
                feedback_text="Final approve",
            )
        ],
        traces=[
            AgentTrace(
                trace_id="trace-1",
                project_id="proj-feedback",
                run_id="run-feedback",
                agent_id="feedback_memory",
                agent_name="Feedback Memory",
                status="running",
            )
        ],
    )

    with patch("app.agents.mubit_memory_agent.MubitMemoryClient") as client_cls:
        client = client_cls.return_value
        client.remember_short_term = AsyncMock(side_effect=RuntimeError("HTTP 403"))

        result = await MubitMemoryAgent().write_feedback_memory(blackboard)

    assert len(result.memory_updates) == 1
    update = result.memory_updates[0]
    assert update["short_term_updates"]
    assert update["episodic_updates"]
    assert "local only" in update["summary"].lower()
    assert result.traces[-1].output_summary == update["summary"]
    client.remember_short_term.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_reference_blueprint_memory_skips_without_blueprint() -> None:
    blackboard = ProjectBlackboard(
        project_id="proj-empty",
        run_id="run-empty",
        user_id="default-user",
    )

    result = await MubitMemoryAgent().write_reference_blueprint_memory(blackboard)

    assert result.memory_updates == []
