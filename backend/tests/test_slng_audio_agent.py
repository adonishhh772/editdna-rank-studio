import asyncio
from unittest.mock import AsyncMock, patch

from app.agents.slng_audio_agent import SLNGAudioAgent
from app.constants.audio_style import AUDIO_PLAN_VOICEOVER_GAIN_DB
from app.db import create_project, new_id
from app.schemas import EditPlan, RankedClip


def test_slng_audio_agent_applies_reference_gain():
    board = create_project("test-user", "SLNG Gain Test")
    board.edit_plan = EditPlan(
        edit_plan_id=new_id("plan"),
        project_id=board.project_id,
        version=1,
        topic="Test",
        output_aspect_ratio="9:16",
        output_duration_sec=4.0,
        hook_text="Hook",
        outro_text="Outro",
        sections=[
            RankedClip(
                rank=1,
                candidate_id="c1",
                title="Clip",
                source_file_path="/tmp/source.mp4",
                clip_start_sec=0.0,
                clip_end_sec=4.0,
                label_text="#1 Clip",
                reason="Test",
                voiceover_text="First place goes here",
            )
        ],
        captions=[],
        audio_plan={AUDIO_PLAN_VOICEOVER_GAIN_DB: 10.0},
        motion_plan=[],
        transition_plan=[],
        render_settings={},
        reference_blueprint_applied={},
        memory_influence={},
    )

    with patch(
        "app.agents.slng_audio_agent.SLNGAudioClient.generate_voiceover",
        new_callable=AsyncMock,
        return_value="/tmp/raw.wav",
    ), patch(
        "app.agents.slng_audio_agent.apply_audio_gain_db",
        new_callable=AsyncMock,
        return_value="/tmp/boosted.wav",
    ) as gain_mock:
        result = asyncio.run(SLNGAudioAgent().execute(board))

    gain_mock.assert_awaited_once()
    raw_path, boosted_path, gain_db = gain_mock.await_args.args
    assert raw_path == "/tmp/raw.wav"
    assert boosted_path.endswith("_boosted.wav")
    assert gain_db == 10.0
    assert result.edit_plan.audio_plan["voiceover_path"] == "/tmp/boosted.wav"
