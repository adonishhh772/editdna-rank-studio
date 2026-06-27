import re
from typing import Iterable

from app.schemas import CandidateVideo, RankedClip

GENERIC_REASON_MARKERS: tuple[str, ...] = (
    "reference-aligned highlight",
    "using full source",
    "auto-selected from learned preferences",
    "matched reference duration",
    "download for review",
)

STORY_COHERENCE_APPROVAL_THRESHOLD = 0.55
STORY_COHERENCE_NEEDS_IMPROVEMENT_THRESHOLD = 0.65

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "about",
        "number",
        "rank",
        "clip",
        "video",
        "shows",
        "showing",
        "moment",
        "segment",
        "highlight",
    }
)


def is_generic_analysis_reason(reason: str | None) -> bool:
    if not reason or not reason.strip():
        return True
    lowered = reason.lower()
    return any(marker in lowered for marker in GENERIC_REASON_MARKERS)


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9']+", text.lower())
    return {token for token in tokens if len(token) > 2 and token not in _STOP_WORDS}


def _first_sentence(text: str, max_length: int = 90) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    sentence_match = re.split(r"[.!?]\s+", cleaned, maxsplit=1)
    first = sentence_match[0].strip()
    if len(first) <= max_length:
        return first
    return first[: max_length - 3].rstrip() + "..."


def derive_video_moment_title(candidate: CandidateVideo) -> str:
    if candidate.video_moment_title and candidate.video_moment_title.strip():
        return candidate.video_moment_title.strip()

    highlight = candidate.highlight_reason
    if highlight and not is_generic_analysis_reason(highlight):
        return _first_sentence(highlight)

    reason = candidate.reason
    if reason and not is_generic_analysis_reason(reason):
        return _first_sentence(reason)

    concept = candidate.concept.strip()
    if concept:
        return concept[:90]

    rank = candidate.recommended_rank or 0
    return f"Rank #{rank} moment"


def compute_story_coherence_score(
    voiceover_text: str,
    highlight_reason: str | None,
    concept: str,
    video_moment_title: str,
) -> float:
    voiceover_tokens = _tokenize(voiceover_text)
    if not voiceover_tokens:
        return 0.0

    reference_texts = [video_moment_title, concept]
    if highlight_reason and not is_generic_analysis_reason(highlight_reason):
        reference_texts.append(highlight_reason)

    reference_tokens: set[str] = set()
    for reference_text in reference_texts:
        reference_tokens.update(_tokenize(reference_text))

    if not reference_tokens:
        return 0.35

    overlap = voiceover_tokens & reference_tokens
    overlap_ratio = len(overlap) / max(len(voiceover_tokens), 1)

    concept_tokens = _tokenize(concept)
    concept_overlap = len(voiceover_tokens & concept_tokens) / max(len(concept_tokens), 1)

    score = 0.55 * overlap_ratio + 0.45 * concept_overlap
    if is_generic_analysis_reason(highlight_reason):
        score *= 0.75
    return min(max(score, 0.0), 1.0)


def compute_weighted_overall_score(candidate: CandidateVideo) -> float:
    story_coherence = candidate.story_coherence_score
    if story_coherence <= 0.0:
        story_coherence = compute_story_coherence_score(
            voiceover_text=build_rank_voiceover_text(
                candidate.recommended_rank or 1,
                derive_video_moment_title(candidate),
            ),
            highlight_reason=candidate.highlight_reason,
            concept=candidate.concept,
            video_moment_title=derive_video_moment_title(candidate),
        )

    score = (
        0.24 * candidate.topic_match_score
        + 0.18 * candidate.visual_quality_score
        + 0.12 * candidate.reference_style_fit_score
        + 0.10 * candidate.motion_energy_score
        + 0.10 * candidate.text_relevance_score
        + 0.14 * story_coherence
        + 0.07 * candidate.audio_quality_score
        + 0.05 * candidate.source_safety_score
    )
    return min(max(score, 0.0), 1.0)


def build_rank_voiceover_text(rank: int, video_moment_title: str) -> str:
    return f"Number {rank}: {video_moment_title}"


def build_rank_label_text(rank: int, video_moment_title: str) -> str:
    return f"#{rank} {video_moment_title}"


def build_section_voiceover_text(
    rank: int,
    candidate: CandidateVideo,
    *,
    highlight_reason: str | None = None,
) -> str:
    video_moment_title = derive_video_moment_title(candidate)
    return build_rank_voiceover_text(rank, video_moment_title)


def enrich_candidate_story_fields(candidate: CandidateVideo) -> CandidateVideo:
    video_moment_title = derive_video_moment_title(candidate)
    rank = candidate.recommended_rank or 1
    voiceover_text = build_rank_voiceover_text(rank, video_moment_title)
    story_coherence = compute_story_coherence_score(
        voiceover_text=voiceover_text,
        highlight_reason=candidate.highlight_reason,
        concept=candidate.concept,
        video_moment_title=video_moment_title,
    )

    candidate.video_moment_title = video_moment_title
    candidate.story_coherence_score = story_coherence
    candidate.overall_score = compute_weighted_overall_score(candidate)
    return candidate


def enrich_ranked_clip_story_fields(section: RankedClip, candidate: CandidateVideo) -> RankedClip:
    video_moment_title = derive_video_moment_title(candidate)
    rank = section.rank
    voiceover_text = build_rank_voiceover_text(rank, video_moment_title)
    story_coherence = compute_story_coherence_score(
        voiceover_text=voiceover_text,
        highlight_reason=section.highlight_reason or candidate.highlight_reason,
        concept=candidate.concept,
        video_moment_title=video_moment_title,
    )

    section.video_moment_title = video_moment_title
    section.source_video_title = candidate.title
    section.title = video_moment_title
    section.label_text = build_rank_label_text(rank, video_moment_title)
    section.caption_text = section.label_text
    section.voiceover_text = voiceover_text
    section.story_coherence_score = story_coherence
    section.needs_improvement = story_coherence < STORY_COHERENCE_NEEDS_IMPROVEMENT_THRESHOLD

    candidate.story_coherence_score = story_coherence
    candidate.overall_score = compute_weighted_overall_score(candidate)

    analysis_scores = dict(section.analysis_scores)
    analysis_scores["story_coherence"] = story_coherence
    analysis_scores["overall"] = candidate.overall_score
    section.analysis_scores = analysis_scores
    return section


def evaluate_edit_plan_story_coherence(sections: Iterable[RankedClip]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    story_ready = True

    for section in sections:
        coherence = section.story_coherence_score
        if coherence < STORY_COHERENCE_APPROVAL_THRESHOLD:
            story_ready = False
            label = section.video_moment_title or section.label_text
            issues.append(
                f"Rank #{section.rank} ({label}): voiceover does not match the video moment "
                f"(story coherence {coherence:.0%})"
            )
        elif section.needs_improvement:
            label = section.video_moment_title or section.label_text
            issues.append(
                f"Rank #{section.rank} ({label}): story could be clearer "
                f"(coherence {coherence:.0%}) — consider regenerating"
            )

        if is_generic_analysis_reason(section.reason):
            story_ready = False
            issues.append(
                f"Rank #{section.rank}: clip summary is generic — re-analyse or pick another source"
            )

    return story_ready, issues
