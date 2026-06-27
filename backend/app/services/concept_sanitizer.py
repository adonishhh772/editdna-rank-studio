import re

CITATION_PATTERN = re.compile(r"\[\d+\]")
MARKDOWN_EMPHASIS_PATTERN = re.compile(r"\*\*[^*]+\*\*")
URL_LABEL_PATTERN = re.compile(r"^\*\*(youtube|tiktok|instagram|video)\s*url:\*\*", re.IGNORECASE)
GENERIC_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
TRUNCATED_TITLE_PATTERN = re.compile(r"(…|\.\.\.)\s*$")
RANKING_HEADLINE_PATTERN = re.compile(r"^ranking\s+(the\s+)?", re.IGNORECASE)
MIN_CONCEPT_LENGTH = 5
MAX_CONCEPT_LENGTH = 120
MAX_SEARCH_CONCEPT_LENGTH = 80


def is_valid_research_concept(raw: str) -> bool:
    normalized = raw.strip()
    if len(normalized) < MIN_CONCEPT_LENGTH or len(normalized) > MAX_CONCEPT_LENGTH:
        return False
    if URL_LABEL_PATTERN.match(normalized):
        return False
    if GENERIC_URL_PATTERN.match(normalized):
        return False
    if normalized.lower() in {"youtube", "tiktok", "shorts", "video", "url"}:
        return False
    if CITATION_PATTERN.fullmatch(normalized.replace(" ", "")):
        return False
    if MARKDOWN_EMPHASIS_PATTERN.fullmatch(normalized):
        return False
    if "**" in normalized and CITATION_PATTERN.search(normalized):
        return False
    if TRUNCATED_TITLE_PATTERN.search(normalized):
        return False
    return True


URL_LABEL_ONLY_PATTERN = re.compile(
    r"^(youtube|tiktok|instagram|video|url)\s*(url)?\s*:?\s*$",
    re.IGNORECASE,
)


def sanitize_research_concept(raw: str) -> str | None:
    normalized = re.sub(r"\*\*", "", raw.strip())
    normalized = CITATION_PATTERN.sub("", normalized).strip(" -•*:")
    normalized = re.sub(r"\s+", " ", normalized)
    if URL_LABEL_ONLY_PATTERN.match(normalized):
        return None
    if not is_valid_research_concept(normalized):
        return None
    return normalized


def build_fallback_concepts(topic: str, ranking_count: int) -> list[str]:
    trimmed_topic = topic.strip() or "topic"
    return [
        f"{trimmed_topic} highlight #{index}"
        for index in range(1, ranking_count + 1)
    ]


def normalize_research_concepts(
    raw_concepts: list[str],
    *,
    topic: str,
    ranking_count: int,
) -> list[str]:
    cleaned: list[str] = []
    for raw in raw_concepts:
        concept = sanitize_research_concept(raw)
        if concept and concept not in cleaned:
            cleaned.append(concept)

    if len(cleaned) < ranking_count:
        for fallback in build_fallback_concepts(topic, ranking_count):
            if fallback not in cleaned:
                cleaned.append(fallback)
            if len(cleaned) >= ranking_count:
                break

    return cleaned[: max(ranking_count, 1)]


def _trim_search_query(query: str) -> str:
    normalized = re.sub(r"\s+", " ", query).strip()
    if len(normalized) > MAX_SEARCH_CONCEPT_LENGTH:
        normalized = normalized[:MAX_SEARCH_CONCEPT_LENGTH].rsplit(" ", 1)[0]
    return normalized or "shorts clip"


def build_topic_shorts_search_query(topic: str, slot_rank: int | None = None) -> str:
    trimmed_topic = topic.strip()
    rank_suffix = f" #{slot_rank}" if slot_rank is not None else ""
    if trimmed_topic:
        return _trim_search_query(f"{trimmed_topic} shorts{rank_suffix}")
    return _trim_search_query(f"viral shorts{rank_suffix}")


def build_platform_search_concept(concept: str, topic: str, slot_rank: int | None = None) -> str:
    trimmed_topic = topic.strip()
    rank_suffix = f" #{slot_rank}" if slot_rank is not None else ""
    sanitized = sanitize_research_concept(concept)

    if trimmed_topic:
        query = f"{trimmed_topic} shorts{rank_suffix}"
    else:
        query = f"viral shorts{rank_suffix}"

    if (
        sanitized
        and not TRUNCATED_TITLE_PATTERN.search(sanitized)
        and not RANKING_HEADLINE_PATTERN.match(sanitized)
        and sanitized.lower() not in query.lower()
    ):
        short_hook = sanitized[:48].strip()
        if short_hook:
            query = f"{trimmed_topic} {short_hook} shorts{rank_suffix}".strip()

    return _trim_search_query(query)
