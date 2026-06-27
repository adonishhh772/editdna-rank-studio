import asyncio
import re
import time
from typing import Any

from tavily import TavilyClient

from app.config import get_settings
from app.constants.tavily import (
    RESEARCH_MAX_POLL_ATTEMPTS,
    RESEARCH_POLL_INTERVAL_SECONDS,
    TOPIC_RESEARCH_INPUT_TEMPLATE,
    TOPIC_SEARCH_QUERY_TEMPLATE,
)
from app.constants.video_sources import (
    ALLOWED_STOCK_SEARCH_DOMAINS,
    MAX_SEARCH_RESULTS_PER_QUERY,
    TIKTOK_SEARCH_DOMAINS,
    YOUTUBE_SEARCH_MODE_ANY,
    platform_search_queries_for_mode,
    tiktok_search_queries,
    YOUTUBE_SEARCH_DOMAINS,
    is_downloadable_platform_url,
    is_single_tiktok_video_url,
    is_single_youtube_video_url,
)
from app.schemas import TopicResearch
from app.services.concept_sanitizer import normalize_research_concepts, sanitize_research_concept

LIST_ITEM_PATTERN = re.compile(r"^(?:\d+[.)]\s+|[\-*•]\s+)(.+)$")


class TavilyResearchClient:
    def __init__(self) -> None:
        settings = get_settings()
        settings.require_key("TAVILY_API_KEY")
        self.client = TavilyClient(api_key=settings.tavily_api_key)

    async def research_topic(
        self,
        topic: str,
        ranking_count: int,
        project_id: str,
        youtube_search_mode: str = YOUTUBE_SEARCH_MODE_ANY,
    ) -> TopicResearch:
        normalized_topic = topic.strip()
        search_task = asyncio.to_thread(self._search_topic, normalized_topic, ranking_count)
        research_task = asyncio.to_thread(self._research_topic_focused, normalized_topic, ranking_count)
        search_data, research_data = await asyncio.gather(search_task, research_task)

        concepts = self.build_concepts_from_sources(search_data, research_data, ranking_count, topic=normalized_topic)
        source_urls = self.collect_source_urls_from_sources(search_data, research_data)

        summary_parts = []
        if search_data.get("answer"):
            summary_parts.append(search_data["answer"])
        if research_data and research_data.get("content"):
            summary_parts.append(research_data["content"][:2000])

        return self.build_topic_research(
            project_id=project_id,
            topic=normalized_topic,
            ranking_count=ranking_count,
            research_summary="\n\n".join(summary_parts) or f"Research completed for: {normalized_topic}",
            candidate_concepts=concepts,
            source_urls=source_urls,
            search_results=search_data.get("results", []),
            youtube_search_mode=youtube_search_mode,
        )

    def build_topic_research(
        self,
        *,
        project_id: str,
        topic: str,
        ranking_count: int,
        research_summary: str,
        candidate_concepts: list[str],
        source_urls: list[str],
        search_results: list[dict[str, Any]],
        youtube_search_mode: str = YOUTUBE_SEARCH_MODE_ANY,
        reference_video_format: str = "unknown",
        reference_video_orientation: str = "unknown",
        aspect_ratio_hint: str = "unknown",
        target_candidate_duration_sec: float | None = None,
        rank_segment_duration_sec: float | None = None,
        max_source_duration_sec: float | None = None,
        min_source_duration_sec: float | None = None,
    ) -> TopicResearch:
        normalized_format = reference_video_format if reference_video_format in {"shorts", "regular"} else "unknown"
        normalized_orientation = (
            reference_video_orientation if reference_video_orientation in {"mobile", "landscape"} else "unknown"
        )
        normalized_search_mode = (
            youtube_search_mode if youtube_search_mode in {"shorts", "regular", "any"} else YOUTUBE_SEARCH_MODE_ANY
        )
        return TopicResearch(
            project_id=project_id,
            topic=topic,
            ranking_count=ranking_count,
            research_summary=research_summary,
            candidate_concepts=candidate_concepts,
            source_urls=source_urls,
            search_results=search_results,
            reference_video_format=normalized_format,
            reference_video_orientation=normalized_orientation,
            youtube_search_mode=normalized_search_mode,
            aspect_ratio_hint=aspect_ratio_hint,
            target_candidate_duration_sec=target_candidate_duration_sec,
            rank_segment_duration_sec=rank_segment_duration_sec,
            max_source_duration_sec=max_source_duration_sec,
            min_source_duration_sec=min_source_duration_sec,
        )

    def build_concepts_from_sources(
        self,
        search_data: dict[str, Any],
        research_data: dict[str, Any] | None,
        ranking_count: int,
        topic: str = "",
    ) -> list[str]:
        raw = self._extract_concepts(search_data, research_data, ranking_count)
        return normalize_research_concepts(raw, topic=topic, ranking_count=ranking_count)

    def collect_source_urls_from_sources(
        self,
        search_data: dict[str, Any],
        research_data: dict[str, Any] | None,
    ) -> list[str]:
        return self._collect_source_urls(search_data, research_data)

    def _search_topic(self, topic: str, ranking_count: int) -> dict[str, Any]:
        query = TOPIC_SEARCH_QUERY_TEMPLATE.format(topic=topic, ranking_count=ranking_count)
        return self.client.search(
            query=query,
            search_depth="basic",
            max_results=10,
            include_answer="basic",
        )

    async def search_topic_async(self, topic: str, ranking_count: int) -> dict[str, Any]:
        return await asyncio.to_thread(self._search_topic, topic, ranking_count)

    async def research_topic_focused_async(
        self,
        topic: str,
        ranking_count: int,
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._research_topic_focused, topic, ranking_count)

    def _research_topic_focused(self, topic: str, ranking_count: int) -> dict[str, Any] | None:
        research_input = TOPIC_RESEARCH_INPUT_TEMPLATE.format(topic=topic, ranking_count=ranking_count)
        try:
            task = self.client.research(input=research_input, model="mini")
            request_id = task.get("request_id")
            if not request_id:
                return None
            for _ in range(RESEARCH_MAX_POLL_ATTEMPTS):
                result = self.client.get_research(request_id)
                status = result.get("status")
                if status == "completed":
                    return result
                if status == "failed":
                    return None
                time.sleep(RESEARCH_POLL_INTERVAL_SECONDS)
        except Exception:
            return None
        return None

    def _collect_source_urls(
        self,
        search_data: dict[str, Any],
        research_data: dict[str, Any] | None,
    ) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for item in search_data.get("results", []):
            url = item.get("url", "")
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        if research_data:
            for source in research_data.get("sources", []):
                url = source.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    urls.append(url)
        return urls[:20]

    def _extract_concepts(
        self,
        search_data: dict[str, Any],
        research_data: dict[str, Any] | None,
        ranking_count: int,
    ) -> list[str]:
        concepts: list[str] = []

        if research_data:
            content = research_data.get("content", "")
            for item in self._parse_list_items_from_text(content):
                self._append_concept(concepts, item)

            for source in research_data.get("sources", [])[: ranking_count * 2]:
                title = str(source.get("title") or source.get("url", "")).strip()
                self._append_concept(concepts, title)

        for item in search_data.get("results", []):
            title = item.get("title", "").strip()
            self._append_concept(concepts, title)

        return concepts[: max(ranking_count * 3, 10)]

    def _parse_list_items_from_text(self, text: str) -> list[str]:
        parsed: list[str] = []
        for line in text.splitlines():
            match = LIST_ITEM_PATTERN.match(line.strip())
            if not match:
                continue
            item = match.group(1).strip()
            if 5 <= len(item) <= 120:
                parsed.append(item)
        return parsed

    def _append_concept(self, concepts: list[str], candidate: str) -> None:
        normalized = sanitize_research_concept(candidate)
        if not normalized or normalized in concepts:
            return
        concepts.append(normalized)

    async def search_candidate_sources(self, topic: str, concepts: list[str]) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_candidate_sources_sync, topic, concepts)

    def _search_candidate_sources_sync(self, topic: str, concepts: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for concept in concepts[:8]:
            query = f"{concept} {topic} demo product footage"
            response = self.client.search(
                query=query,
                search_depth="basic",
                max_results=3,
            )
            for item in response.get("results", []):
                results.append(item)
        return results

    async def extract_source_context(self, urls: list[str]) -> list[dict[str, Any]]:
        if not urls:
            return []
        return await asyncio.to_thread(self._extract_sync, urls[:10])

    async def search_stock_video_urls(self, query: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_stock_video_urls_sync, query)

    async def search_platform_video_urls(self, concept: str, topic: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_platform_video_urls_sync, concept, topic)

    async def search_platform_video_urls_for_query(self, query: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_youtube_urls_for_query_sync, query)

    async def search_youtube_video_urls(
        self,
        concept: str,
        topic: str,
        search_mode: str | None = None,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._search_youtube_video_urls_sync,
            concept,
            topic,
            search_mode,
        )

    async def search_tiktok_video_urls(
        self,
        concept: str,
        topic: str,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_tiktok_video_urls_sync, concept, topic)

    def _search_tiktok_urls_for_query_sync(self, query: str) -> list[dict[str, Any]]:
        response = self.client.search(
            query=query,
            search_depth="basic",
            max_results=MAX_SEARCH_RESULTS_PER_QUERY,
            include_domains=list(TIKTOK_SEARCH_DOMAINS),
        )
        return response.get("results", [])

    def _search_tiktok_video_urls_sync(self, concept: str, topic: str) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for template in tiktok_search_queries():
            query = template.format(concept=concept, topic=topic)[:400]
            for item in self._search_tiktok_urls_for_query_sync(query):
                url = item.get("url", "")
                if (
                    not url
                    or url in seen_urls
                    or not is_downloadable_platform_url(url)
                    or not is_single_tiktok_video_url(url)
                ):
                    continue
                seen_urls.add(url)
                merged.append(item)
        return merged

    async def search_open_web_videos(self, query: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_open_web_videos_sync, query)

    def _search_stock_video_urls_sync(self, query: str) -> list[dict[str, Any]]:
        response = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=8,
            include_domains=ALLOWED_STOCK_SEARCH_DOMAINS,
        )
        return response.get("results", [])

    def _search_youtube_urls_for_query_sync(self, query: str) -> list[dict[str, Any]]:
        response = self.client.search(
            query=query,
            search_depth="basic",
            max_results=MAX_SEARCH_RESULTS_PER_QUERY,
            include_domains=list(YOUTUBE_SEARCH_DOMAINS),
        )
        return response.get("results", [])

    def _search_youtube_video_urls_sync(
        self,
        concept: str,
        topic: str,
        search_mode: str | None = None,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        query_templates = platform_search_queries_for_mode(search_mode or YOUTUBE_SEARCH_MODE_ANY)

        for template in query_templates:
            query = template.format(concept=concept, topic=topic)[:400]
            for item in self._search_youtube_urls_for_query_sync(query):
                url = item.get("url", "")
                if (
                    not url
                    or url in seen_urls
                    or not is_downloadable_platform_url(url)
                    or not is_single_youtube_video_url(url)
                ):
                    continue
                seen_urls.add(url)
                merged.append(item)

        return merged

    def _search_platform_video_urls_sync(self, concept: str, topic: str) -> list[dict[str, Any]]:
        return self._search_youtube_video_urls_sync(concept, topic)

    def _search_open_web_videos_sync(self, query: str) -> list[dict[str, Any]]:
        response = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=10,
        )
        return response.get("results", [])

    def _extract_sync(self, urls: list[str]) -> list[dict[str, Any]]:
        response = self.client.extract(urls=urls, extract_depth="basic")
        return response.get("results", [])
