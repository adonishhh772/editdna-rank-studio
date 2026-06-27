from app.constants.video_constraints import VIDEO_PREFERENCES_MEMORY_KEY
from app.services.preference_learning_service import (
    compute_preference_learning_adjustment,
    format_video_preferences_for_analysis,
    summarize_preferences_for_ui,
)


def _memory_with_preferences(preferences: dict) -> dict:
    return {VIDEO_PREFERENCES_MEMORY_KEY: preferences}


def test_approved_example_boosts_similar_duration_and_orientation():
    memory = _memory_with_preferences(
        {
            "approved_examples": [
                {
                    "concept": "intro hook",
                    "duration_sec": 22.0,
                    "orientation": "mobile",
                    "aspect_ratio_hint": "9:16",
                }
            ],
            "rejected_examples": [],
            "notes": [],
            "preferred_duration_sec": 22.0,
        }
    )

    delta, reasons = compute_preference_learning_adjustment(
        duration_sec=21.0,
        orientation="mobile",
        aspect_ratio_hint="9:16",
        memory_context=memory,
        target_duration_sec=20.0,
    )

    assert delta > 0
    assert "Matches approved duration profile" in reasons
    assert "Matches approved orientation" in reasons


def test_rejected_example_penalizes_similar_clips():
    memory = _memory_with_preferences(
        {
            "approved_examples": [],
            "rejected_examples": [
                {
                    "concept": "long landscape clip",
                    "duration_sec": 720.0,
                    "orientation": "landscape",
                    "aspect_ratio_hint": "16:9",
                }
            ],
            "notes": ["Rejected long landscape clip: 720s landscape clip not preferred"],
        }
    )

    delta, reasons = compute_preference_learning_adjustment(
        duration_sec=718.0,
        orientation="landscape",
        aspect_ratio_hint="16:9",
        memory_context=memory,
        target_duration_sec=20.0,
    )

    assert delta < 0
    assert any("rejected" in reason.lower() for reason in reasons)


def test_format_video_preferences_includes_notes_and_examples():
    memory = _memory_with_preferences(
        {
            "approved_examples": [{"concept": "rank 5", "duration_sec": 18.0, "orientation": "mobile"}],
            "rejected_examples": [{"concept": "rank 3", "duration_sec": 600.0, "orientation": "landscape"}],
            "notes": ["Approved rank 5: 18s mobile clip preferred"],
            "blocked_orientations": ["landscape"],
            "max_duration_sec": 45.0,
            "preferred_duration_sec": 18.0,
        }
    )

    prompt = format_video_preferences_for_analysis(memory)

    assert "Learned video preferences" not in prompt
    assert "Approved rank 5: 18s mobile clip preferred" in prompt
    assert "rank 5" in prompt
    assert "rank 3" in prompt
    assert "Blocked orientations: landscape" in prompt
    assert "Preferred full-source duration: ~18s" in prompt


def test_summarize_preferences_for_ui():
    memory = _memory_with_preferences(
        {
            "approved_examples": [{"concept": "a", "duration_sec": 20.0}],
            "rejected_examples": [],
            "notes": ["Approved a"],
            "preferred_duration_sec": 20.0,
        }
    )

    summary = summarize_preferences_for_ui(memory)

    assert summary["has_learning"] is True
    assert summary["preferred_duration_sec"] == 20.0
    assert len(summary["approved_examples"]) == 1
