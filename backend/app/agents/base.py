from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.agents.workflow.stream_events import node_display_label
from app.blackboard import ProjectBlackboard
from app.db import new_id, save_blackboard, utc_now
from app.schemas import AgentTrace, DownloadEvent


class BaseAgent(ABC):
    agent_id: str
    agent_name: str

    async def execute(
        self,
        blackboard: ProjectBlackboard,
        *,
        parent_agent_id: str | None = None,
        swarm: bool = False,
    ) -> ProjectBlackboard:
        trace = AgentTrace(
            trace_id=new_id("trace"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            visible_reasoning=node_display_label(self.agent_id),
        )
        if parent_agent_id:
            trace.metadata["parent_agent_id"] = parent_agent_id
        if swarm or parent_agent_id:
            trace.metadata["swarm"] = True
        blackboard.traces.append(trace)
        save_blackboard(blackboard)

        try:
            blackboard = await self.run(blackboard)
            trace.status = "complete"
            trace.completed_at = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            trace.status = "failed"
            trace.error = str(exc)
            trace.completed_at = datetime.now(timezone.utc).isoformat()
            raise
        finally:
            save_blackboard(blackboard)
            await self._write_trace_memory(blackboard, trace)

        return blackboard

    @abstractmethod
    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        pass

    def active_trace(self, blackboard: ProjectBlackboard) -> AgentTrace:
        return blackboard.traces[-1]

    def log_tool_call(self, blackboard: ProjectBlackboard, tool_name: str, payload: dict[str, Any]) -> None:
        trace = self.active_trace(blackboard)
        trace.tool_calls.append(
            {
                "tool": tool_name,
                "timestamp": utc_now(),
                **payload,
            }
        )
        save_blackboard(blackboard)

    def record_download_event(
        self,
        blackboard: ProjectBlackboard,
        concept: str,
        stage: str,
        candidate_id: str | None = None,
        platform: str | None = None,
        search_query: str | None = None,
        source_url: str | None = None,
        local_file_path: str | None = None,
        file_size_bytes: int | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DownloadEvent:
        event = DownloadEvent(
            event_id=new_id("dl"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            candidate_id=candidate_id,
            concept=concept,
            stage=stage,
            platform=platform,
            search_query=search_query,
            source_url=source_url,
            local_file_path=local_file_path,
            file_size_bytes=file_size_bytes,
            error=error,
            metadata=metadata or {},
            created_at=utc_now(),
        )
        blackboard.download_events.append(event)
        self.log_tool_call(
            blackboard,
            "download_pipeline",
            {
                "stage": stage,
                "concept": concept,
                "candidate_id": candidate_id,
                "platform": platform,
                "source_url": source_url,
                "local_file_path": local_file_path,
                "error": error,
            },
        )
        return event

    async def _write_trace_memory(self, blackboard: ProjectBlackboard, trace: AgentTrace) -> None:
        try:
            from app.integrations.mubit_client import MubitMemoryClient

            client = MubitMemoryClient(run_id=blackboard.run_id)
            await client.remember_trace(
                user_id=blackboard.user_id,
                project_id=blackboard.project_id,
                run_id=blackboard.run_id,
                trace=trace.model_dump(),
            )
        except Exception:
            pass
