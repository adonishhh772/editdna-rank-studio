from typing import Any

from app.constants.audio_style import (
    AUDIO_MIX_MODE_BALANCED,
    AUDIO_MIX_MODE_MUSIC_DRIVEN,
    AUDIO_MIX_MODE_VOICE_FIRST,
    AUDIO_PLAN_MIX_MODE,
    AUDIO_PLAN_NORMALIZE,
    AUDIO_PLAN_REFERENCE_AUDIO_STYLE,
    AUDIO_PLAN_REFERENCE_DRIVEN,
    AUDIO_PLAN_SOURCE_GAIN_DB,
    AUDIO_PLAN_SOURCE_WEIGHT,
    AUDIO_PLAN_VOICEOVER_GAIN_DB,
    AUDIO_PLAN_VOICEOVER_WEIGHT,
    AUDIO_STYLE_ENERGY,
    AUDIO_STYLE_ESTIMATED_STYLE,
    AUDIO_STYLE_HAS_SPEECH,
    AUDIO_STYLE_MAX_VOLUME_DB,
    AUDIO_STYLE_MEAN_VOLUME_DB,
    AUDIO_STYLE_MOOD,
    AUDIO_STYLE_VOICE_PROMINENCE,
    AUDIO_VOICE_PROMINENCE_HIGH,
    AUDIO_VOICE_PROMINENCE_LOW,
    AUDIO_VOICE_PROMINENCE_MEDIUM,
    DEFAULT_SOURCE_GAIN_DB,
    DEFAULT_SOURCE_WEIGHT,
    DEFAULT_VOICEOVER_GAIN_DB,
    DEFAULT_VOICEOVER_WEIGHT,
    HIGH_SOURCE_GAIN_DB,
    HIGH_SOURCE_WEIGHT,
    HIGH_VOICEOVER_GAIN_DB,
    HIGH_VOICEOVER_WEIGHT,
    LOUD_MEAN_VOLUME_DB_THRESHOLD,
    LOW_SOURCE_GAIN_DB,
    LOW_SOURCE_WEIGHT,
    LOW_VOICEOVER_GAIN_DB,
    LOW_VOICEOVER_WEIGHT,
    MEDIUM_MEAN_VOLUME_DB_THRESHOLD,
)
from app.schemas import ReferenceBlueprint


def derive_voice_prominence(audio_style: dict[str, Any]) -> str:
    mean_volume_db = audio_style.get(AUDIO_STYLE_MEAN_VOLUME_DB)
    if isinstance(mean_volume_db, (int, float)):
        if mean_volume_db >= LOUD_MEAN_VOLUME_DB_THRESHOLD:
            return AUDIO_VOICE_PROMINENCE_HIGH
        if mean_volume_db >= MEDIUM_MEAN_VOLUME_DB_THRESHOLD:
            return AUDIO_VOICE_PROMINENCE_MEDIUM
        return AUDIO_VOICE_PROMINENCE_LOW

    estimated_style = str(audio_style.get(AUDIO_STYLE_ESTIMATED_STYLE) or "")
    if estimated_style == AUDIO_MIX_MODE_VOICE_FIRST:
        return AUDIO_VOICE_PROMINENCE_HIGH
    if estimated_style == AUDIO_MIX_MODE_MUSIC_DRIVEN:
        return AUDIO_VOICE_PROMINENCE_LOW

    energy = str(audio_style.get(AUDIO_STYLE_ENERGY) or audio_style.get(AUDIO_STYLE_MOOD) or "").lower()
    if energy in {"high", "energetic", "loud", "intense"}:
        return AUDIO_VOICE_PROMINENCE_HIGH
    if energy in {"low", "calm", "quiet", "soft"}:
        return AUDIO_VOICE_PROMINENCE_LOW

    return AUDIO_VOICE_PROMINENCE_MEDIUM


def resolve_mix_profile(voice_prominence: str) -> tuple[str, float, float, float, float]:
    if voice_prominence == AUDIO_VOICE_PROMINENCE_HIGH:
        return (
            AUDIO_MIX_MODE_VOICE_FIRST,
            HIGH_VOICEOVER_WEIGHT,
            HIGH_SOURCE_WEIGHT,
            HIGH_VOICEOVER_GAIN_DB,
            HIGH_SOURCE_GAIN_DB,
        )
    if voice_prominence == AUDIO_VOICE_PROMINENCE_LOW:
        return (
            AUDIO_MIX_MODE_MUSIC_DRIVEN,
            LOW_VOICEOVER_WEIGHT,
            LOW_SOURCE_WEIGHT,
            LOW_VOICEOVER_GAIN_DB,
            LOW_SOURCE_GAIN_DB,
        )
    return (
        AUDIO_MIX_MODE_BALANCED,
        DEFAULT_VOICEOVER_WEIGHT,
        DEFAULT_SOURCE_WEIGHT,
        DEFAULT_VOICEOVER_GAIN_DB,
        DEFAULT_SOURCE_GAIN_DB,
    )


def build_audio_plan_from_reference(blueprint: ReferenceBlueprint | None) -> dict[str, Any]:
    if blueprint is None:
        return {
            AUDIO_PLAN_MIX_MODE: AUDIO_MIX_MODE_BALANCED,
            AUDIO_PLAN_VOICEOVER_WEIGHT: DEFAULT_VOICEOVER_WEIGHT,
            AUDIO_PLAN_SOURCE_WEIGHT: DEFAULT_SOURCE_WEIGHT,
            AUDIO_PLAN_VOICEOVER_GAIN_DB: DEFAULT_VOICEOVER_GAIN_DB,
            AUDIO_PLAN_SOURCE_GAIN_DB: DEFAULT_SOURCE_GAIN_DB,
            AUDIO_PLAN_NORMALIZE: True,
            AUDIO_PLAN_REFERENCE_DRIVEN: False,
        }

    audio_style = dict(blueprint.audio_style or {})
    voice_prominence = derive_voice_prominence(audio_style)
    mix_mode, voiceover_weight, source_weight, voiceover_gain_db, source_gain_db = resolve_mix_profile(
        voice_prominence
    )

    return {
        AUDIO_PLAN_MIX_MODE: mix_mode,
        AUDIO_PLAN_VOICEOVER_WEIGHT: voiceover_weight,
        AUDIO_PLAN_SOURCE_WEIGHT: source_weight,
        AUDIO_PLAN_VOICEOVER_GAIN_DB: voiceover_gain_db,
        AUDIO_PLAN_SOURCE_GAIN_DB: source_gain_db,
        AUDIO_PLAN_NORMALIZE: True,
        AUDIO_PLAN_REFERENCE_DRIVEN: True,
        AUDIO_PLAN_REFERENCE_AUDIO_STYLE: {
            AUDIO_STYLE_VOICE_PROMINENCE: voice_prominence,
            AUDIO_STYLE_MEAN_VOLUME_DB: audio_style.get(AUDIO_STYLE_MEAN_VOLUME_DB),
            AUDIO_STYLE_MAX_VOLUME_DB: audio_style.get(AUDIO_STYLE_MAX_VOLUME_DB),
            AUDIO_STYLE_ESTIMATED_STYLE: audio_style.get(AUDIO_STYLE_ESTIMATED_STYLE),
            AUDIO_STYLE_HAS_SPEECH: audio_style.get(AUDIO_STYLE_HAS_SPEECH),
            AUDIO_STYLE_MOOD: audio_style.get(AUDIO_STYLE_MOOD),
            AUDIO_STYLE_ENERGY: audio_style.get(AUDIO_STYLE_ENERGY),
        },
    }


def build_audio_mix_filter(audio_plan: dict[str, Any]) -> str:
    source_gain_db = float(audio_plan.get(AUDIO_PLAN_SOURCE_GAIN_DB) or DEFAULT_SOURCE_GAIN_DB)
    voiceover_gain_db = float(audio_plan.get(AUDIO_PLAN_VOICEOVER_GAIN_DB) or DEFAULT_VOICEOVER_GAIN_DB)
    source_weight = float(audio_plan.get(AUDIO_PLAN_SOURCE_WEIGHT) or DEFAULT_SOURCE_WEIGHT)
    voiceover_weight = float(audio_plan.get(AUDIO_PLAN_VOICEOVER_WEIGHT) or DEFAULT_VOICEOVER_WEIGHT)

    return (
        f"[0:a]volume={source_gain_db:.2f}dB[a0];"
        f"[1:a]volume={voiceover_gain_db:.2f}dB[a1];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=2:"
        f"weights={source_weight:.3f} {voiceover_weight:.3f}[aout]"
    )
