from typing import Any

DEFAULT_CAPTION_FONT_SIZE = 48
HIGH_CAPTION_FONT_SIZE = 64
LOW_CAPTION_FONT_SIZE = 36


def resolve_caption_font_size(caption_style: dict[str, Any] | None) -> int:
    if not caption_style:
        return DEFAULT_CAPTION_FONT_SIZE

    for key in ("font_size", "fontsize", "size"):
        raw_value = caption_style.get(key)
        if isinstance(raw_value, (int, float)) and raw_value > 0:
            return int(raw_value)

    prominence = str(caption_style.get("prominence") or "").lower()
    if prominence == "high":
        return HIGH_CAPTION_FONT_SIZE
    if prominence == "low":
        return LOW_CAPTION_FONT_SIZE
    return DEFAULT_CAPTION_FONT_SIZE


def build_render_settings_from_blueprint(blueprint: dict[str, Any] | None) -> dict[str, Any]:
    if not blueprint:
        return {"width": 1080, "height": 1920, "fps": 30, "caption_font_size": DEFAULT_CAPTION_FONT_SIZE}

    caption_style = blueprint.get("caption_style")
    caption_font_size = resolve_caption_font_size(
        caption_style if isinstance(caption_style, dict) else None
    )
    return {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "caption_font_size": caption_font_size,
        "reference_caption_style": caption_style if isinstance(caption_style, dict) else {},
        "reference_motion_style": blueprint.get("motion_style") if isinstance(blueprint.get("motion_style"), dict) else {},
        "reference_pacing_style": blueprint.get("pacing_style") if isinstance(blueprint.get("pacing_style"), dict) else {},
    }
