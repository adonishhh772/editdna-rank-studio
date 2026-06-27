import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from mubit import Client

from app.config import get_settings


class MubitMemoryClient:
    MEMORY_SCOPE_SHORT = "short_term"
    MEMORY_SCOPE_EPISODIC = "episodic"
    MEMORY_SCOPE_LONG = "long_term"
    QUERY_MODE_AGENT_ROUTED = "AGENT_ROUTED"
    DIRECT_QUERY_LANE_SEMANTIC_SEARCH = "SEMANTIC_SEARCH"

    def __init__(self, run_id: str) -> None:
        settings = get_settings()
        settings.require_key("MUBIT_API_KEY")
        self.settings = settings
        self.client = Client(
            api_key=settings.mubit_api_key,
            run_id=run_id,
            transport="auto",
        )

    async def _poll_ingest(self, job_id: str | None) -> None:
        if not job_id:
            return

        def poll() -> None:
            for _ in range(20):
                job = self.client.get_ingest_job(job_id)
                if job.get("done"):
                    return
                time.sleep(0.5)

        await asyncio.to_thread(poll)

    def _base_metadata(
        self,
        project_id: str,
        run_id: str,
        agent_id: str,
        memory_scope: str,
        topic: str | None = None,
        feedback_type: str | None = None,
        confidence: float = 0.8,
    ) -> dict[str, Any]:
        return {
            "project_id": project_id,
            "run_id": run_id,
            "agent_id": agent_id,
            "memory_scope": memory_scope,
            "video_type": "ranking_video",
            "topic": topic or "",
            "feedback_type": feedback_type or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": confidence,
        }

    async def remember_short_term(
        self,
        user_id: str,
        project_id: str,
        run_id: str,
        agent_id: str,
        content: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._remember(user_id, project_id, run_id, agent_id, content, metadata, "fact", "session")

    async def remember_episodic(
        self,
        user_id: str,
        project_id: str,
        run_id: str,
        agent_id: str,
        content: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._remember(user_id, project_id, run_id, agent_id, content, metadata, "lesson", "session")

    async def remember_long_term(
        self,
        user_id: str,
        project_id: str,
        run_id: str,
        agent_id: str,
        content: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._remember(user_id, project_id, run_id, agent_id, content, metadata, "lesson", "global")

    async def _remember(
        self,
        user_id: str,
        project_id: str,
        run_id: str,
        agent_id: str,
        content: str,
        metadata: dict[str, Any],
        intent: str,
        lesson_scope: str,
    ) -> dict[str, Any]:
        def write() -> dict[str, Any]:
            result = self.client.remember(
                session_id=run_id,
                agent_id=agent_id,
                user_id=user_id,
                content=content,
                intent=intent,
                lesson_scope=lesson_scope,
                metadata={**metadata, "project_id": project_id},
            )
            return result if isinstance(result, dict) else {"result": result}

        payload = await asyncio.to_thread(write)
        await self._poll_ingest(payload.get("job_id"))
        return payload

    async def recall_context(
        self,
        user_id: str,
        project_id: str,
        topic: str,
        video_type: str,
    ) -> dict[str, Any]:
        def recall() -> dict[str, Any]:
            query = f"User preferences for {video_type} about {topic}. Editing style, pacing, captions, audio."
            answer = self.client.recall(
                session_id=project_id,
                user_id=user_id,
                query=query,
                entry_types=["fact", "lesson", "rule"],
                mode=self.QUERY_MODE_AGENT_ROUTED,
                direct_lane=self.DIRECT_QUERY_LANE_SEMANTIC_SEARCH,
            )
            context = self.client.get_context(
                session_id=project_id,
                query=query,
                mode="summary",
                max_token_budget=400,
            )
            return {
                "final_answer": answer.get("final_answer", ""),
                "evidence": answer.get("evidence", []),
                "section_summaries": context.get("section_summaries", []),
                "context_block": context.get("context_block", ""),
            }

        return await asyncio.to_thread(recall)

    async def remember_trace(
        self,
        user_id: str,
        project_id: str,
        run_id: str,
        trace: dict[str, Any],
    ) -> dict[str, Any]:
        content = (
            f"Agent {trace.get('agent_name')} ({trace.get('agent_id')}) "
            f"status={trace.get('status')}: {trace.get('output_summary') or trace.get('input_summary')}"
        )
        metadata = self._base_metadata(
            project_id=project_id,
            run_id=run_id,
            agent_id=str(trace.get("agent_id", "unknown")),
            memory_scope=self.MEMORY_SCOPE_SHORT,
            confidence=0.7,
        )
        return await self.remember_short_term(
            user_id=user_id,
            project_id=project_id,
            run_id=run_id,
            agent_id=str(trace.get("agent_id", "unknown")),
            content=content,
            metadata=metadata,
        )
