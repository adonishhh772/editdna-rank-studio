from typing import Any

from app.constants.feedback import (
    EXPLICIT_PREFERENCE_MARKERS,
    FEEDBACK_SENTIMENT_NEGATIVE,
    FEEDBACK_SENTIMENT_NEUTRAL,
    FEEDBACK_SENTIMENT_POSITIVE,
    FEEDBACK_TYPE_AI_SUGGESTED,
    FEEDBACK_TYPE_APPROVE,
    FEEDBACK_TYPE_FINAL_APPROVE,
    FEEDBACK_TYPE_NEGATIVE,
    FEEDBACK_TYPE_POSITIVE,
    FEEDBACK_TYPE_REJECT,
    NEGATIVE_TEXT_MARKERS,
    POSITIVE_TEXT_MARKERS,
)
from app.schemas import FeedbackEvent


POSITIVE_FEEDBACK_TYPES: frozenset[str] = frozenset(
    {
        FEEDBACK_TYPE_APPROVE,
        FEEDBACK_TYPE_FINAL_APPROVE,
        FEEDBACK_TYPE_POSITIVE,
    }
)

NEGATIVE_FEEDBACK_TYPES: frozenset[str] = frozenset(
    {
        FEEDBACK_TYPE_REJECT,
        FEEDBACK_TYPE_NEGATIVE,
        FEEDBACK_TYPE_AI_SUGGESTED,
    }
)


def classify_feedback_sentiment(
    feedback_text: str | None,
    feedback_type: str,
) -> str:
    if feedback_type in POSITIVE_FEEDBACK_TYPES:
        return FEEDBACK_SENTIMENT_POSITIVE
    if feedback_type in NEGATIVE_FEEDBACK_TYPES:
        return FEEDBACK_SENTIMENT_NEGATIVE

    normalized = (feedback_text or "").strip().lower()
    if not normalized:
        return FEEDBACK_SENTIMENT_NEUTRAL

    negative_hits = sum(1 for marker in NEGATIVE_TEXT_MARKERS if marker in normalized)
    positive_hits = sum(1 for marker in POSITIVE_TEXT_MARKERS if marker in normalized)

    if negative_hits > positive_hits:
        return FEEDBACK_SENTIMENT_NEGATIVE
    if positive_hits > negative_hits:
        return FEEDBACK_SENTIMENT_POSITIVE
    return FEEDBACK_SENTIMENT_NEUTRAL


def build_memory_scope_updates(
    feedback: FeedbackEvent,
    sentiment: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    content = feedback.feedback_text or feedback.feedback_type
    short_term: list[dict[str, Any]] = [
        {"content": content, "type": feedback.feedback_type, "sentiment": sentiment}
    ]
    episodic: list[dict[str, Any]] = []
    long_term: list[dict[str, Any]] = []

    if sentiment == FEEDBACK_SENTIMENT_POSITIVE:
        episodic.append({"content": f"Successful output: {content}", "sentiment": sentiment})
        long_term.append({"content": f"Repeat this style: {content}", "sentiment": sentiment})
    elif sentiment == FEEDBACK_SENTIMENT_NEGATIVE:
        episodic.append({"content": f"Improve next time: {content}", "sentiment": sentiment})
        if feedback.feedback_text and any(
            marker in feedback.feedback_text.lower() for marker in EXPLICIT_PREFERENCE_MARKERS
        ):
            long_term.append({"content": feedback.feedback_text, "sentiment": sentiment})
    elif feedback.feedback_text and any(
        marker in feedback.feedback_text.lower() for marker in EXPLICIT_PREFERENCE_MARKERS
    ):
        long_term.append({"content": feedback.feedback_text, "sentiment": sentiment})

    if feedback.feedback_type in {FEEDBACK_TYPE_APPROVE, FEEDBACK_TYPE_REJECT, FEEDBACK_TYPE_FINAL_APPROVE}:
        episodic.append({"content": content, "sentiment": sentiment})

    return short_term, episodic, long_term


def feedback_memory_summary(
    *,
    short_term_count: int,
    episodic_count: int,
    long_term_count: int,
    sentiment: str,
    mubit_synced: bool,
) -> str:
    sync_note = "" if mubit_synced else " (local only — Mubit sync failed)"
    intent = {
        FEEDBACK_SENTIMENT_POSITIVE: "remembered as a preference to repeat",
        FEEDBACK_SENTIMENT_NEGATIVE: "stored as an improvement to apply next time",
        FEEDBACK_SENTIMENT_NEUTRAL: "stored for this session",
    }.get(sentiment, "stored")
    return (
        f"Feedback {intent}: {short_term_count} short-term, "
        f"{episodic_count} episodic, {long_term_count} long-term updates{sync_note}"
    )
