from app.constants.audio_style import (
    AUDIO_MIX_MODE_VOICE_FIRST,
    AUDIO_PLAN_REFERENCE_DRIVEN,
    AUDIO_PLAN_VOICEOVER_GAIN_DB,
    AUDIO_PLAN_VOICEOVER_WEIGHT,
    AUDIO_STYLE_MEAN_VOLUME_DB,
    HIGH_VOICEOVER_GAIN_DB,
    HIGH_VOICEOVER_WEIGHT,
)
from app.schemas import ReferenceBlueprint
from app.services.reference_audio_plan_service import (
    build_audio_mix_filter,
    build_audio_plan_from_reference,
    derive_voice_prominence,
)
from app.services.reference_render_style_service import (
    build_render_settings_from_blueprint,
    resolve_caption_font_size,
)


def _reference_blueprint(**overrides: object) -> ReferenceBlueprint:
    payload = {
        "blueprint_id": "bp-1",
        "project_id": "proj-1",
        "video_type": "ranking_video",
        "aspect_ratio": "9:16",
        "duration_sec": 30.0,
        "ranking_count": 5,
        "ranking_order": "5_to_1",
        "hook_duration_sec": 3.0,
        "average_item_duration_sec": 4.0,
        "outro_duration_sec": 2.0,
        "section_order": [],
        "caption_style": {},
        "text_overlay_style": {},
        "transition_style": {},
        "audio_style": {},
        "motion_style": {},
        "pacing_style": {},
        "hook_style": "question",
        "rank_reveal_style": "countdown",
        "final_rank_drama_level": "medium",
        "confidence": 0.9,
    }
    payload.update(overrides)
    return ReferenceBlueprint(**payload)


def test_derive_voice_prominence_from_loud_reference():
    prominence = derive_voice_prominence({AUDIO_STYLE_MEAN_VOLUME_DB: -10.0})
    assert prominence == "high"


def test_build_audio_plan_boosts_voice_for_loud_reference():
    blueprint = _reference_blueprint(
        audio_style={AUDIO_STYLE_MEAN_VOLUME_DB: -12.0, "estimated_style": "voice_first"},
    )
    plan = build_audio_plan_from_reference(blueprint)

    assert plan[AUDIO_PLAN_REFERENCE_DRIVEN] is True
    assert plan["mix_mode"] == AUDIO_MIX_MODE_VOICE_FIRST
    assert plan[AUDIO_PLAN_VOICEOVER_WEIGHT] == HIGH_VOICEOVER_WEIGHT
    assert plan[AUDIO_PLAN_VOICEOVER_GAIN_DB] == HIGH_VOICEOVER_GAIN_DB


def test_build_audio_mix_filter_uses_reference_weights():
    plan = build_audio_plan_from_reference(
        _reference_blueprint(audio_style={AUDIO_STYLE_MEAN_VOLUME_DB: -12.0}),
    )
    mix_filter = build_audio_mix_filter(plan)

    assert "volume=10.00dB" in mix_filter
    assert "weights=0.220 0.780" in mix_filter


def test_resolve_caption_font_size_from_prominence():
    assert resolve_caption_font_size({"prominence": "high"}) == 64
    assert resolve_caption_font_size({"font_size": 56}) == 56


def test_build_render_settings_carries_caption_style():
    settings = build_render_settings_from_blueprint(
        {"caption_style": {"prominence": "high", "motion_style": {"zoom": True}}}
    )
    assert settings["caption_font_size"] == 64
    assert settings["reference_caption_style"]["prominence"] == "high"
