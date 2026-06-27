import pytest
import shutil
from pathlib import Path
from unittest.mock import patch

from app.constants.demo import DEMO_PACK_RECORDING
from app.constants.candidate_review import SLOT_STATUS_AWAITING_APPROVAL
from app.constants.feedback import FEEDBACK_TYPE_TEXT
from app.db import create_project, new_id
from app.schemas import CandidateReviewSlot, FeedbackEvent
from app.services.demo_pack_loader import load_demo_pack
from app.services.demo_replay_service import DemoReplayService


@pytest.mark.asyncio
async def test_analyse_reference_builds_blueprint_with_pack_ranking_count():
    pack = load_demo_pack(DEMO_PACK_RECORDING)
    demo = DemoReplayService(pack)
    blackboard = create_project("demo-user", "Demo Test")
    blackboard.reference_video_url = pack.youtube_url

    updated = await demo.analyse_reference(blackboard)

    assert updated.reference_blueprint is not None
    assert updated.reference_blueprint.ranking_count == 5
    assert updated.stage == "reference_analysed"
    assert len(updated.traces) >= 4
    assert updated.memory_context.get("demo_mode") is not True
    memory_text = " ".join(
        str(item.get("content", ""))
        for update in updated.memory_updates
        for field in ("short_term_updates", "episodic_updates", "long_term_updates")
        for item in (update.get(field) or [])
    )
    assert "3D" not in memory_text


@pytest.mark.asyncio
async def test_research_topic_sets_concepts_for_all_ranks():
    pack = load_demo_pack(DEMO_PACK_RECORDING)
    demo = DemoReplayService(pack)
    blackboard = create_project("demo-user", "Demo Test")
    blackboard.topic = pack.topic
    blackboard.reference_blueprint = (await demo.analyse_reference(blackboard)).reference_blueprint

    updated = await demo.research_topic(blackboard)

    assert updated.topic_research is not None
    assert updated.topic_research.ranking_count == 5
    assert len(updated.topic_research.candidate_concepts) == 5


@pytest.mark.asyncio
async def test_render_copies_final_output_to_project_outputs():
    pack = load_demo_pack(DEMO_PACK_RECORDING)
    demo = DemoReplayService(pack)
    blackboard = create_project("demo-user", "Demo Test")

    fast_render_sec = 0.05
    with patch("app.services.demo_replay_service.DEMO_RENDER_TOTAL_SEC", fast_render_sec):
        rendered = await demo.render(blackboard)

    assert rendered.output_video_path is not None
    assert rendered.stage == "rendered"
    assert Path(rendered.output_video_path).exists()
    render_traces = [trace for trace in rendered.traces if trace.agent_id == "rank_clip_render"]
    assert len(render_traces) >= 1
    assert any(trace.agent_id == "video_stitch" for trace in rendered.traces)


@pytest.mark.asyncio
async def test_prepare_slot_reject_variant_uses_low_scores(tmp_path: Path):
    pack = load_demo_pack(DEMO_PACK_RECORDING)
    reject_source = pack.candidate_files[4]
    reject_target = pack.pack_dir / "candidates" / "rank_3_reject.mp4"
    shutil.copy2(reject_source, reject_target)

    try:
        demo = DemoReplayService(load_demo_pack(DEMO_PACK_RECORDING))
        blackboard = create_project("demo-user", "Reject Demo")
        slot = CandidateReviewSlot(slot_rank=3, concept="Hard-surface mech render")

        first_pass = await demo.prepare_slot(blackboard, slot)

        assert first_pass.selected_candidates[0].topic_match_score < 0.5
        assert first_pass.selected_candidates[0].title == "Off-topic clip — not strong enough for 3D art ranking"
        assert "reject" in first_pass.selected_candidates[0].source_url
        assert slot.status == SLOT_STATUS_AWAITING_APPROVAL
    finally:
        if reject_target.exists():
            reject_target.unlink()


@pytest.mark.asyncio
async def test_prepare_slot_uses_notes_title_for_approved_clip():
    pack = load_demo_pack(DEMO_PACK_RECORDING)
    demo = DemoReplayService(pack)
    blackboard = create_project("demo-user", "Title Demo")
    slot = CandidateReviewSlot(slot_rank=1, concept=pack.rank_concepts[1])

    updated = await demo.prepare_slot(blackboard, slot)
    candidate = updated.selected_candidates[0]

    assert candidate.title == "Hero cinematic 3D scene"
    assert candidate.video_moment_title == "Hero cinematic 3D scene"
    assert not candidate.title.startswith("Rank #")


@pytest.mark.asyncio
async def test_create_edit_plan_applies_studio_ai_feedback_suggestions():
    pack = load_demo_pack(DEMO_PACK_RECORDING)
    demo = DemoReplayService(pack)
    blackboard = create_project("demo-user", "Studio Feedback Demo")
    blackboard.topic = pack.topic
    blackboard.reference_blueprint = (await demo.analyse_reference(blackboard)).reference_blueprint
    blackboard.approved_candidates = []
    for rank_number in range(1, pack.ranking_count + 1):
        slot = CandidateReviewSlot(
            slot_rank=rank_number,
            concept=pack.rank_concepts.get(rank_number, f"Rank #{rank_number}"),
        )
        prepared = await demo.prepare_slot(blackboard, slot)
        blackboard = prepared
        blackboard.approved_candidates.append(prepared.selected_candidates[0])

    first_plan = await demo.create_edit_plan(blackboard)
    assert first_plan.edit_plan is not None
    assert len(first_plan.edit_plan.ai_feedback_suggestions) > 0
    initial_suggestion_count = len(first_plan.edit_plan.ai_feedback_suggestions)
    feedback_text = first_plan.edit_plan.ai_feedback_suggestions[0].feedback_text
    first_plan.feedback_events.append(
        FeedbackEvent(
            feedback_id="fb-test",
            project_id=first_plan.project_id,
            run_id=first_plan.run_id,
            user_id=first_plan.user_id,
            feedback_type="ai_suggested_feedback",
            feedback_text=feedback_text,
        )
    )

    updated = await demo.create_edit_plan(first_plan)
    assert updated.edit_plan is not None
    assert updated.edit_plan.story_ready is True
    assert all(
        suggestion.feedback_text != feedback_text
        for suggestion in updated.edit_plan.ai_feedback_suggestions
    )
    assert "applied_studio_feedback" in updated.edit_plan.memory_influence
    assert updated.edit_plan.hook_text.endswith("refined from your studio feedback")
    assert len(updated.edit_plan.ai_feedback_suggestions) < initial_suggestion_count


@pytest.mark.asyncio
async def test_apply_feedback_builds_memory_summary():
    pack = load_demo_pack(DEMO_PACK_RECORDING)
    demo = DemoReplayService(pack)
    blackboard = create_project("demo-user", "Feedback Demo")
    blackboard.feedback_events.append(
        FeedbackEvent(
            feedback_id=new_id("fb"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            user_id=blackboard.user_id,
            feedback_type=FEEDBACK_TYPE_TEXT,
            feedback_text="Make rank 1 more dramatic",
        )
    )

    updated = await demo.apply_feedback(blackboard)

    assert updated.stage == "feedback_applied"
    assert updated.memory_updates
    summary = updated.memory_updates[-1]["summary"]
    assert "short-term" in summary
    assert "episodic" in summary
    assert "long-term" in summary
