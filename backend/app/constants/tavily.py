TOPIC_SEARCH_QUERY_TEMPLATE = (
    'specific real-world examples of "{topic}" for a top-{ranking_count} ranked video 2026'
)

TOPIC_RESEARCH_INPUT_TEMPLATE = (
    'The user wants a ranked video about: "{topic}". '
    "Identify exactly {ranking_count} distinct, specific, real-world examples of {topic}. "
    "Each item must be a concrete moment, event, person, or incident that can be found as raw Shorts footage. "
    "Return descriptive concept names only — never URL labels, citation markers, or markdown like '**YouTube URL:** [1]'. "
    "Focus only on what the user asked for. "
    "Do not suggest product reviews, unrelated topics, or generic categories."
)

RESEARCH_POLL_INTERVAL_SECONDS = 5
RESEARCH_MAX_POLL_ATTEMPTS = 24
