FEEDBACK_TYPE_APPROVE = "approve"
FEEDBACK_TYPE_REJECT = "reject"
FEEDBACK_TYPE_TEXT = "text_feedback"
FEEDBACK_TYPE_VOICE = "voice_feedback"
FEEDBACK_TYPE_FINAL_APPROVE = "final_approve"
FEEDBACK_TYPE_POSITIVE = "positive_feedback"
FEEDBACK_TYPE_NEGATIVE = "negative_feedback"
FEEDBACK_TYPE_AI_SUGGESTED = "ai_suggested_feedback"

FEEDBACK_SENTIMENT_POSITIVE = "positive"
FEEDBACK_SENTIMENT_NEGATIVE = "negative"
FEEDBACK_SENTIMENT_NEUTRAL = "neutral"

FEEDBACK_SOURCE_STORY_COHERENCE = "story_coherence"
FEEDBACK_SOURCE_LOW_SCORE = "low_score"
FEEDBACK_SOURCE_NEEDS_IMPROVEMENT = "needs_improvement"

FEEDBACK_SEVERITY_INFO = "info"
FEEDBACK_SEVERITY_WARNING = "warning"
FEEDBACK_SEVERITY_CRITICAL = "critical"

LOW_ANALYSIS_SCORE_THRESHOLD = 0.5
LOW_AUDIO_SCORE_THRESHOLD = 0.3
LOW_STORY_COHERENCE_THRESHOLD = 0.65

POSITIVE_TEXT_MARKERS: tuple[str, ...] = (
    "great",
    "love",
    "perfect",
    "good",
    "keep",
    "nice",
    "excellent",
    "approve",
    "works",
    "better",
)

NEGATIVE_TEXT_MARKERS: tuple[str, ...] = (
    "fix",
    "wrong",
    "bad",
    "less",
    "more",
    "reduce",
    "improve",
    "mismatch",
    "dramatic",
    "slower",
    "faster",
    "caption",
    "story",
    "regenerate",
    "not preferred",
    "reject",
)

EXPLICIT_PREFERENCE_MARKERS: tuple[str, ...] = (
    "prefer",
    "always",
    "never",
    "dislike",
    "like",
)
