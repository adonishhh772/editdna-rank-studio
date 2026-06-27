from app.services.concept_sanitizer import (
    build_fallback_concepts,
    build_platform_search_concept,
    build_topic_shorts_search_query,
    is_valid_research_concept,
    normalize_research_concepts,
    sanitize_research_concept,
)


def test_rejects_citation_style_youtube_url_concept():
    assert sanitize_research_concept("**YouTube URL:** [1]") is None
    assert not is_valid_research_concept("**YouTube URL:** [1]")


def test_accepts_real_concept():
    assert sanitize_research_concept("Messi bicycle kick vs Getafe") == "Messi bicycle kick vs Getafe"


def test_normalize_fills_fallbacks_when_research_is_garbage():
    concepts = normalize_research_concepts(
        ["**YouTube URL:** [1]", "**TikTok URL:** [2]"],
        topic="best football moments",
        ranking_count=3,
    )
    assert len(concepts) == 3
    assert all("best football moments" in concept for concept in concepts)


def test_build_fallback_concepts_count():
    assert len(build_fallback_concepts("AI tools", 5)) == 5


def test_rejects_truncated_research_title():
    assert sanitize_research_concept("Ranking the Most EMBARRASSING World Cup 2026 Moments So ...") is None


def test_build_platform_search_concept_from_truncated_title_uses_topic():
    query = build_platform_search_concept(
        "Ranking the Most EMBARRASSING World Cup 2026 Moments So ...",
        "embarrassing videos",
        slot_rank=1,
    )
    assert "embarrassing videos" in query
    assert "shorts" in query.lower()


def test_build_platform_search_concept_topic_first():
    query = build_platform_search_concept("Messi bicycle kick vs Getafe", "football fails", 2)
    assert query.startswith("football fails")
    assert "shorts" in query.lower()
    assert "Messi" in query


def test_build_topic_shorts_search_query():
    query = build_topic_shorts_search_query("awkward moments", 3)
    assert query == "awkward moments shorts #3"
