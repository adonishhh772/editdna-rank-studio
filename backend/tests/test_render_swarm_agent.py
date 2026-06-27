import asyncio
from unittest.mock import AsyncMock, patch

from app.agents.render_swarm_agent import RenderSwarmAgent
from app.db import create_project, new_id
from app.schemas import EditPlan, RankedClip


def _board_with_edit_plan():
    board = create_project("test-user", "Render Swarm Test")
    section = RankedClip(
        rank=5,
        candidate_id="cand-1",
        title="Clip",
        source_file_path="/tmp/source.mp4",
        clip_start_sec=0.0,
        clip_end_sec=4.0,
        label_text="#5 Clip",
        reason="Test clip",
    )
    board.edit_plan = EditPlan(
        edit_plan_id=new_id("plan"),
        project_id=board.project_id,
        version=1,
        topic="Test topic",
        output_aspect_ratio="9:16",
        output_duration_sec=4.0,
        hook_text="Top 5 moments",
        outro_text="Thanks for watching",
        sections=[section],
        captions=[],
        audio_plan={},
        motion_plan=[],
        transition_plan=[],
        render_settings={},
        reference_blueprint_applied={},
        memory_influence={},
    )
    return board


def test_render_swarm_creates_sub_agent_traces():
    board = _board_with_edit_plan()

    with patch(
        "app.agents.render_swarm_agent.render_rank_clip",
        new_callable=AsyncMock,
        return_value="/tmp/render/clip_0/labeled.mp4",
    ), patch(
        "app.agents.render_swarm_agent.stitch_rank_clips",
        new_callable=AsyncMock,
        return_value="/tmp/render/concat.mp4",
    ), patch(
        "app.agents.render_swarm_agent.apply_hook_overlay",
        new_callable=AsyncMock,
        return_value="/tmp/render/with_hook.mp4",
    ), patch(
        "app.agents.render_swarm_agent.finalize_render_output",
        new_callable=AsyncMock,
        return_value="/tmp/output/rendered.mp4",
    ), patch(
        "app.agents.render_swarm_agent.get_video_duration",
        new_callable=AsyncMock,
        return_value=4.0,
    ):
        result = asyncio.run(RenderSwarmAgent().execute(board, swarm=True))

    swarm_traces = [trace for trace in result.traces if trace.metadata.get("swarm")]
    assert any(trace.agent_id == "render_swarm" for trace in swarm_traces)
    assert any(trace.agent_id == "rank_clip_render" for trace in result.traces)
    assert any(trace.agent_id == "video_stitch" for trace in result.traces)
    assert any(trace.agent_id == "audio_mix" for trace in result.traces)
    assert result.output_video_path == "/tmp/output/rendered.mp4"
    assert result.stage == "rendered"
