from app.schemas import ReferenceBlueprint


def build_reference_blueprint_memory_content(blueprint: ReferenceBlueprint) -> str:
    caption_prominence = blueprint.caption_style.get("prominence", "unknown")
    caption_case = blueprint.caption_style.get("case", "unknown")
    pacing_tempo = blueprint.pacing_style.get("tempo", "unknown")
    motion_energy = blueprint.motion_style.get("energy", "unknown")
    audio_notes = blueprint.audio_style.get("mood") or blueprint.audio_style.get("style") or "unspecified"

    return (
        f"Reference ranking video uses {blueprint.ranking_count} ranks in {blueprint.ranking_order} order. "
        f"Hook lasts {blueprint.hook_duration_sec}s with style '{blueprint.hook_style}'. "
        f"Average rank segment is {blueprint.average_item_duration_sec}s, outro {blueprint.outro_duration_sec}s. "
        f"Rank reveal style is '{blueprint.rank_reveal_style}' with {blueprint.final_rank_drama_level} final-rank drama. "
        f"Captions are {caption_prominence} prominence, {caption_case} case. "
        f"Pacing is {pacing_tempo}, motion energy is {motion_energy}, audio mood is {audio_notes}. "
        f"Aspect ratio {blueprint.aspect_ratio}, total duration {blueprint.duration_sec}s."
    )
