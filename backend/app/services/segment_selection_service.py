from app.constants.video_constraints import RANKING_ORDER_5_TO_1
from app.schemas import CandidateVideo, ReferenceBlueprint, ReferenceSection


def rank_segment_duration_for_rank(blueprint: ReferenceBlueprint, rank: int | None) -> float:
    if rank is not None:
        for section in blueprint.section_order:
            if section.rank_number == rank:
                return max(section.end_sec - section.start_sec, blueprint.average_item_duration_sec)
    return blueprint.average_item_duration_sec


def rank_position_ratio(blueprint: ReferenceBlueprint, rank: int | None) -> float:
    total_ranks = max(blueprint.ranking_count, 1)
    rank_index = max((rank or 1) - 1, 0)
    if blueprint.ranking_order == RANKING_ORDER_5_TO_1:
        return rank_index / max(total_ranks - 1, 1)
    return (total_ranks - 1 - rank_index) / max(total_ranks - 1, 1)


def derive_default_segment(
    source_duration: float,
    segment_duration: float,
    blueprint: ReferenceBlueprint,
    rank: int | None,
) -> tuple[float, float, str]:
    if source_duration <= segment_duration * 1.25:
        return 0.0, source_duration, "Using full source — matches reference segment length"

    position_ratio = rank_position_ratio(blueprint, rank)
    available = max(source_duration - segment_duration, 0.0)
    clip_start = available * position_ratio
    clip_end = min(clip_start + segment_duration, source_duration)
    clip_start = max(clip_end - segment_duration, 0.0)

    return (
        clip_start,
        clip_end,
        f"Reference-aligned highlight for rank {rank} ({segment_duration:.1f}s window)",
    )


def apply_reference_segment_to_candidate(
    candidate: CandidateVideo,
    blueprint: ReferenceBlueprint,
) -> CandidateVideo:
    source_duration = candidate.duration_sec or blueprint.duration_sec
    segment_duration = rank_segment_duration_for_rank(blueprint, candidate.recommended_rank)

    if candidate.clip_start_sec is not None and candidate.clip_end_sec is not None:
        clip_start = candidate.clip_start_sec
        clip_end = candidate.clip_end_sec
        reason = candidate.highlight_reason or candidate.reason
    else:
        clip_start, clip_end, reason = derive_default_segment(
            source_duration=source_duration,
            segment_duration=segment_duration,
            blueprint=blueprint,
            rank=candidate.recommended_rank,
        )

    candidate.clip_start_sec = clip_start
    candidate.clip_end_sec = clip_end
    candidate.highlight_reason = reason
    if not candidate.reason or candidate.reason == "Downloaded for review":
        candidate.reason = reason
    return candidate


def reference_section_for_rank(
    blueprint: ReferenceBlueprint,
    rank: int | None,
) -> ReferenceSection | None:
    if rank is None:
        return None
    for section in blueprint.section_order:
        if section.rank_number == rank:
            return section
    return None
