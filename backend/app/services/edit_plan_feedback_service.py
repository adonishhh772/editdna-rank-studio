from app.constants.feedback import (
    FEEDBACK_SEVERITY_CRITICAL,
    FEEDBACK_SEVERITY_INFO,
    FEEDBACK_SEVERITY_WARNING,
    FEEDBACK_SOURCE_LOW_SCORE,
    FEEDBACK_SOURCE_NEEDS_IMPROVEMENT,
    FEEDBACK_SOURCE_STORY_COHERENCE,
    LOW_ANALYSIS_SCORE_THRESHOLD,
    LOW_AUDIO_SCORE_THRESHOLD,
    LOW_STORY_COHERENCE_THRESHOLD,
)
from app.db import new_id
from app.schemas import AiFeedbackSuggestion, RankedClip


def _short_label_from_issue(issue: str) -> str:
    if "voiceover does not match" in issue.lower():
        return "Fix voiceover mismatch"
    if "story could be clearer" in issue.lower():
        return "Improve story clarity"
    if "generic" in issue.lower():
        return "Replace generic clip summary"
    if len(issue) <= 48:
        return issue
    return issue[:45].rstrip() + "..."


def _actionable_from_issue(issue: str) -> str:
    if "voiceover does not match" in issue.lower():
        return "Fix voiceover and story mismatches so each rank matches the video moment"
    if "story could be clearer" in issue.lower():
        return "Improve rank voiceover and highlight text so the story reads clearly"
    if "generic" in issue.lower():
        return "Replace clips with generic summaries and re-analyse candidate footage"
    return issue


def _score_label(score_key: str) -> str:
    labels = {
        "audio_quality": "audio quality",
        "visual_quality": "visual quality",
        "topic_match": "topic match",
        "story_coherence": "story coherence",
        "motion_energy": "motion energy",
        "text_relevance": "text relevance",
    }
    return labels.get(score_key, score_key.replace("_", " "))


def build_ai_edit_plan_feedback_suggestions(
    *,
    story_issues: list[str],
    sections: list[RankedClip],
) -> list[AiFeedbackSuggestion]:
    suggestions: list[AiFeedbackSuggestion] = []
    covered_ranks: set[int] = set()

    for issue in story_issues:
        severity = FEEDBACK_SEVERITY_WARNING
        if "does not match" in issue.lower() or "generic" in issue.lower():
            severity = FEEDBACK_SEVERITY_CRITICAL
        suggestions.append(
            AiFeedbackSuggestion(
                suggestion_id=new_id("ai-fb"),
                label=_short_label_from_issue(issue),
                feedback_text=_actionable_from_issue(issue),
                severity=severity,
                source=FEEDBACK_SOURCE_STORY_COHERENCE,
            )
        )

    for section in sections:
        rank = section.rank
        scores = section.analysis_scores or {}
        label = section.video_moment_title or section.label_text or f"Rank #{rank}"

        if section.needs_improvement and rank not in covered_ranks:
            covered_ranks.add(rank)
            coherence = section.story_coherence_score
            suggestions.append(
                AiFeedbackSuggestion(
                    suggestion_id=new_id("ai-fb"),
                    label=f"Improve rank #{rank} story",
                    feedback_text=(
                        f"Improve rank #{rank} ({label}): story coherence is "
                        f"{coherence:.0%} — align voiceover with the clip moment"
                    ),
                    severity=FEEDBACK_SEVERITY_WARNING,
                    source=FEEDBACK_SOURCE_NEEDS_IMPROVEMENT,
                    rank=rank,
                )
            )

        audio_score = scores.get("audio_quality")
        if isinstance(audio_score, (int, float)) and audio_score < LOW_AUDIO_SCORE_THRESHOLD:
            suggestions.append(
                AiFeedbackSuggestion(
                    suggestion_id=new_id("ai-fb"),
                    label=f"Fix rank #{rank} audio",
                    feedback_text=(
                        f"Rank #{rank} ({label}) has weak audio ({audio_score:.0%}) — "
                        "prefer clips with clearer sound or reduce reliance on silent footage"
                    ),
                    severity=FEEDBACK_SEVERITY_INFO,
                    source=FEEDBACK_SOURCE_LOW_SCORE,
                    rank=rank,
                )
            )

        for score_key in ("visual_quality", "topic_match", "story_coherence"):
            score_value = scores.get(score_key)
            if not isinstance(score_value, (int, float)):
                continue
            if score_value >= LOW_ANALYSIS_SCORE_THRESHOLD:
                continue
            if score_key == "story_coherence" and score_value >= LOW_STORY_COHERENCE_THRESHOLD:
                continue
            suggestions.append(
                AiFeedbackSuggestion(
                    suggestion_id=new_id("ai-fb"),
                    label=f"Boost rank #{rank} {_score_label(score_key)}",
                    feedback_text=(
                        f"Rank #{rank} ({label}) has low {_score_label(score_key)} "
                        f"({score_value:.0%}) — pick a stronger clip or adjust the edit"
                    ),
                    severity=FEEDBACK_SEVERITY_INFO,
                    source=FEEDBACK_SOURCE_LOW_SCORE,
                    rank=rank,
                )
            )

        if rank == 1:
            drama_score = scores.get("motion_energy")
            if isinstance(drama_score, (int, float)) and drama_score < LOW_ANALYSIS_SCORE_THRESHOLD:
                suggestions.append(
                    AiFeedbackSuggestion(
                        suggestion_id=new_id("ai-fb"),
                        label="Make number 1 more dramatic",
                        feedback_text="Make number 1 more dramatic with stronger motion and reveal energy",
                        severity=FEEDBACK_SEVERITY_WARNING,
                        source=FEEDBACK_SOURCE_LOW_SCORE,
                        rank=1,
                    )
                )

    deduped: list[AiFeedbackSuggestion] = []
    seen_labels: set[str] = set()
    for suggestion in suggestions:
        if suggestion.label in seen_labels:
            continue
        seen_labels.add(suggestion.label)
        deduped.append(suggestion)

    return deduped[:8]
