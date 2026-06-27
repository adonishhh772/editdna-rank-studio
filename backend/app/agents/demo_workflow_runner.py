import asyncio
from collections.abc import AsyncIterator

from app.agents.workflow.stream_events import (
    blackboard_activity_signature,
    build_stream_snapshot,
)
from app.blackboard import ProjectBlackboard
from app.constants.workflow import (
    STAGE_ANALYSE_REFERENCE,
    STAGE_COMPARE,
    STAGE_CREATE_EDIT_PLAN,
    STAGE_DISCOVER_CANDIDATES,
    STAGE_FEEDBACK,
    STAGE_REGENERATE,
    STAGE_RENDER,
    STAGE_RESEARCH_TOPIC,
)
from app.db import load_blackboard, save_blackboard
from app.schemas import FeedbackEvent
from app.services.demo_replay_service import DemoReplayService


class DemoWorkflowRunner:
    _STAGE_HANDLERS = {
        STAGE_ANALYSE_REFERENCE: "analyse_reference",
        STAGE_RESEARCH_TOPIC: "research_topic",
        STAGE_DISCOVER_CANDIDATES: "discover_candidates",
        STAGE_CREATE_EDIT_PLAN: "create_edit_plan",
        STAGE_RENDER: "render",
        STAGE_COMPARE: "compare",
        STAGE_FEEDBACK: "apply_feedback",
        STAGE_REGENERATE: "regenerate",
    }

    def __init__(self) -> None:
        self._demo = DemoReplayService.active()

    async def _invoke_stage(
        self,
        stage_name: str,
        blackboard: ProjectBlackboard,
    ) -> ProjectBlackboard:
        handler_name = self._STAGE_HANDLERS.get(stage_name)
        if handler_name is None:
            raise RuntimeError(f"Unsupported demo stage: {stage_name}")
        handler = getattr(self._demo, handler_name)
        updated = await handler(blackboard)
        save_blackboard(updated)
        return updated

    async def stream_stage(
        self,
        stage_name: str,
        blackboard: ProjectBlackboard,
    ) -> AsyncIterator[dict]:
        project_id = blackboard.project_id
        event_queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
        stage_finished = asyncio.Event()
        stage_error: Exception | None = None

        async def run_stage() -> None:
            nonlocal stage_error
            try:
                await self._invoke_stage(stage_name, blackboard)
            except Exception as exc:
                stage_error = exc
            finally:
                stage_finished.set()

        async def poll_blackboard() -> None:
            current_board = load_blackboard(project_id) or blackboard
            last_signature = blackboard_activity_signature(current_board)
            while not stage_finished.is_set():
                await asyncio.sleep(0.35)
                polled_board = load_blackboard(project_id)
                if polled_board is None:
                    continue
                signature = blackboard_activity_signature(polled_board)
                if signature != last_signature:
                    last_signature = signature
                    await event_queue.put(("progress", None))
            await stage_finished.wait()

        stage_task = asyncio.create_task(run_stage())
        poll_task = asyncio.create_task(poll_blackboard())

        try:
            while not stage_finished.is_set() or not event_queue.empty():
                try:
                    event_kind, node_name = await asyncio.wait_for(event_queue.get(), timeout=0.45)
                except asyncio.TimeoutError:
                    continue

                current_board = load_blackboard(project_id) or blackboard
                yield build_stream_snapshot(current_board, event_kind, stage_name, node_name)

            await stage_task
            if stage_error is not None:
                raise stage_error

            final_board = load_blackboard(project_id) or blackboard
            save_blackboard(final_board)
            complete_event = build_stream_snapshot(final_board, "complete", stage_name)
            complete_event["blackboard"] = final_board.model_dump()
            yield complete_event
        finally:
            poll_task.cancel()
            try:
                await poll_task
            except asyncio.CancelledError:
                pass
            if not stage_task.done():
                stage_task.cancel()
                try:
                    await stage_task
                except asyncio.CancelledError:
                    pass

    async def analyse_reference(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_ANALYSE_REFERENCE, blackboard)

    async def research_topic(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_RESEARCH_TOPIC, blackboard)

    async def discover_candidates(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_DISCOVER_CANDIDATES, blackboard)

    async def discover_and_analyse_candidates(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self.discover_candidates(blackboard)

    async def select_ranking(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        raise RuntimeError("Demo mode uses sequential candidate review instead of bulk ranking")

    async def create_edit_plan(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_CREATE_EDIT_PLAN, blackboard)

    async def render(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_RENDER, blackboard)

    async def compare(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_COMPARE, blackboard)

    async def apply_feedback_and_learn(
        self,
        blackboard: ProjectBlackboard,
        feedback: FeedbackEvent,
    ) -> ProjectBlackboard:
        blackboard.feedback_events.append(feedback)
        save_blackboard(blackboard)
        return await self._invoke_stage(STAGE_FEEDBACK, blackboard)

    async def regenerate(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_REGENERATE, blackboard)

    async def clear_human_gate(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._demo.clear_human_gate(blackboard)

    async def resume_after_human_gate(self, project_id: str, stage_name: str) -> ProjectBlackboard:
        board = load_blackboard(project_id)
        if board is None:
            raise RuntimeError("Project not found")
        return await self.clear_human_gate(board)
