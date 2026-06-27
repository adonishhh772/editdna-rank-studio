from app.constants.feedback import (
    FEEDBACK_SENTIMENT_NEGATIVE,
    FEEDBACK_SENTIMENT_POSITIVE,
    FEEDBACK_TYPE_AI_SUGGESTED,
    FEEDBACK_TYPE_FINAL_APPROVE,
    FEEDBACK_TYPE_TEXT,
)
from app.db import new_id, utc_now
from app.schemas import FeedbackEvent, RankedClip
from app.services.edit_plan_feedback_service import build_ai_edit_plan_feedback_suggestions
from app.services.feedback_learning_service import (
    build_memory_scope_updates,
    classify_feedback_sentiment,
)


def test_build_ai_feedback_from_story_issues():
    section = RankedClip(
        rank=5,
        candidate_id="cand-1",
        title="Downloaded from tiktok",
        source_file_path="/tmp/a.mp4",
        clip_start_sec=50.93,
        clip_end_sec=57.03,
        label_text="#5 Downloaded from tiktok",
        voiceover_text="Number 5: Downloaded from tiktok",
        reason="Reference-aligned highlight for rank 5 (6.6s window).",
        story_coherence_score=0.41,
        needs_improvement=True,
        analysis_scores={
            "audio_quality": 0.0,
            "story_coherence": 0.41,
            "overall": 0.52,
        },
    )

    suggestions = build_ai_edit_plan_feedback_suggestions(
        story_issues=[
            "Rank #5 (Downloaded from tiktok): voiceover does not match the video moment (story coherence 41%)"
        ],
        sections=[section],
    )

    assert suggestions
    assert any("Fix voiceover mismatch" in item.label for item in suggestions)
    assert any(item.rank == 5 for item in suggestions)


def test_classify_negative_text_feedback():
    sentiment = classify_feedback_sentiment(
        "Fix story mismatch and make number 1 more dramatic",
        FEEDBACK_TYPE_TEXT,
    )
    assert sentiment == FEEDBACK_SENTIMENT_NEGATIVE


def test_classify_positive_final_approve():
    sentiment = classify_feedback_sentiment("Final approve", FEEDBACK_TYPE_FINAL_APPROVE)
    assert sentiment == FEEDBACK_SENTIMENT_POSITIVE


def test_negative_feedback_writes_improvement_memory():
    feedback = FeedbackEvent(
        feedback_id=new_id("fb"),
        project_id="proj-1",
        run_id="run-1",
        user_id="user-1",
        feedback_type=FEEDBACK_TYPE_AI_SUGGESTED,
        feedback_text="Fix voiceover and story mismatches",
        created_at=utc_now(),
    )

    short_term, episodic, long_term = build_memory_scope_updates(
        feedback,
        FEEDBACK_SENTIMENT_NEGATIVE,
    )

    assert short_term
    assert episodic
    assert any("Improve next time" in item["content"] for item in episodic)
