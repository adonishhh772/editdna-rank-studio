from unittest.mock import MagicMock, patch

import pytest

from app.constants.tavily import TOPIC_RESEARCH_INPUT_TEMPLATE, TOPIC_SEARCH_QUERY_TEMPLATE
from app.integrations.tavily_client import TavilyResearchClient


@pytest.fixture
def mock_tavily_client():
    with patch("app.integrations.tavily_client.TavilyClient") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        with patch("app.integrations.tavily_client.get_settings") as mock_settings:
            settings = MagicMock()
            settings.tavily_api_key = "test-key"
            settings.require_key = MagicMock()
            mock_settings.return_value = settings
            yield mock_instance


@pytest.mark.asyncio
async def test_research_topic_uses_topic_focused_search_and_research(mock_tavily_client):
    mock_tavily_client.search.return_value = {
        "answer": "Found several embarrassing award moments.",
        "results": [
            {"title": "Critics Choice Awards awkward moments", "url": "https://example.com/article"},
        ],
    }
    mock_tavily_client.research.return_value = {"request_id": "req_123"}
    mock_tavily_client.get_research.return_value = {
        "status": "completed",
        "content": (
            "1. Celebrity trips on Critics Choice red carpet\n"
            "2. Awkward acceptance speech at Critics Choice Awards\n"
        ),
        "sources": [
            {"title": "Critics Choice 2026 red carpet fails", "url": "https://example.com/source"},
        ],
    }

    client = TavilyResearchClient()
    research = await client.research_topic(
        topic="embarrassing moments",
        ranking_count=6,
        project_id="proj_test",
    )

    search_query = mock_tavily_client.search.call_args.kwargs["query"]
    assert search_query == TOPIC_SEARCH_QUERY_TEMPLATE.format(
        topic="embarrassing moments",
        ranking_count=6,
    )
    research_input = mock_tavily_client.research.call_args.kwargs["input"]
    assert research_input == TOPIC_RESEARCH_INPUT_TEMPLATE.format(
        topic="embarrassing moments",
        ranking_count=6,
    )
    assert research.candidate_concepts[0] == "Celebrity trips on Critics Choice red carpet"
    assert "Critics Choice Awards awkward moments" in research.candidate_concepts


def test_extract_concepts_prefers_research_list_items(mock_tavily_client):
    client = TavilyResearchClient()
    concepts = client._extract_concepts(
        search_data={
            "results": [
                {"title": "Long unrelated article headline about something else entirely"},
            ]
        },
        research_data={
            "content": "1. Golden Globes wardrobe malfunction\n2. Oscars presenter flub",
            "sources": [],
        },
        ranking_count=6,
    )

    assert concepts[0] == "Golden Globes wardrobe malfunction"
    assert concepts[1] == "Oscars presenter flub"


def test_search_youtube_video_urls_uses_include_domains(mock_tavily_client):
    mock_tavily_client.search.return_value = {
        "results": [
            {
                "url": "https://www.youtube.com/watch?v=abc123",
                "title": "Awkward Critics Choice Moments",
                "score": 0.9,
            },
            {
                "url": "https://www.youtube.com/channel/UCabc123",
                "title": "Channel page",
                "score": 0.8,
            },
        ]
    }

    client = TavilyResearchClient()
    results = client._search_youtube_video_urls_sync(
        concept="Critics Choice Awards awkward moments",
        topic="embarrassing moments",
    )

    assert mock_tavily_client.search.call_count == 3
    first_call_kwargs = mock_tavily_client.search.call_args_list[0].kwargs
    assert first_call_kwargs["include_domains"] == ["youtube.com", "youtu.be", "m.youtube.com"]
    assert len(results) == 1
    assert results[0]["url"] == "https://www.youtube.com/watch?v=abc123"


def test_search_youtube_video_urls_shorts_mode_uses_shorts_queries(mock_tavily_client):
    mock_tavily_client.search.return_value = {"results": []}

    client = TavilyResearchClient()
    client._search_youtube_video_urls_sync(
        concept="award fails",
        topic="embarrassing moments",
        search_mode="shorts",
    )

    first_query = mock_tavily_client.search.call_args_list[0].kwargs["query"]
    assert "shorts" in first_query.lower()
