import asyncio
from collections.abc import AsyncIterator

from langgraph.graph.state import CompiledStateGraph

from app.agents.workflow.graphs import build_full_pipeline_graph, build_stage_graphs
from app.agents.workflow.checkpointer import get_checkpointer
from app.agents.workflow.state import WorkflowState
from app.agents.workflow.stream_events import (
    blackboard_activity_signature,
    build_stream_snapshot,
)
from app.blackboard import ProjectBlackboard
from app.db import load_blackboard
from app.constants.workflow import (
    STAGE_ANALYSE_REFERENCE,
    STAGE_COMPARE,
    STAGE_CREATE_EDIT_PLAN,
    STAGE_DISCOVER_CANDIDATES,
    STAGE_FEEDBACK,
    STAGE_REGENERATE,
    STAGE_RENDER,
    STAGE_RESEARCH_TOPIC,
    STAGE_SELECT_RANKING,
)
from app.db import save_blackboard
from app.schemas import FeedbackEvent


class LangGraphRunner:
    def __init__(self) -> None:
        checkpointer = get_checkpointer()
        self._stage_graphs: dict[str, CompiledStateGraph] = build_stage_graphs(checkpointer)
        self._full_pipeline_graph: CompiledStateGraph = build_full_pipeline_graph(checkpointer)

    def _run_config(self, project_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": project_id}}

    async def _invoke_stage(
        self,
        stage_name: str,
        blackboard: ProjectBlackboard,
    ) -> ProjectBlackboard:
        graph = self._stage_graphs[stage_name]
        result: WorkflowState = await graph.ainvoke(
            {"blackboard": blackboard},
            config=self._run_config(blackboard.project_id),
        )
        updated = result["blackboard"]
        save_blackboard(updated)
        return updated

    async def stream_stage(
        self,
        stage_name: str,
        blackboard: ProjectBlackboard,
    ) -> AsyncIterator[dict]:
        graph = self._stage_graphs[stage_name]
        project_id = blackboard.project_id
        config = self._run_config(project_id)
        event_queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
        graph_finished = asyncio.Event()
        graph_error: Exception | None = None

        async def run_graph() -> None:
            nonlocal graph_error
            try:
                async for chunk in graph.astream(
                    {"blackboard": blackboard},
                    config=config,
                    stream_mode="updates",
                ):
                    for node_name in chunk:
                        await event_queue.put(("node_complete", node_name))
            except Exception as exc:
                graph_error = exc
            finally:
                graph_finished.set()

        async def poll_blackboard() -> None:
            current_board = load_blackboard(project_id) or blackboard
            last_signature = blackboard_activity_signature(current_board)
            while not graph_finished.is_set():
                await asyncio.sleep(0.35)
                polled_board = load_blackboard(project_id)
                if polled_board is None:
                    continue
                signature = blackboard_activity_signature(polled_board)
                if signature != last_signature:
                    last_signature = signature
                    await event_queue.put(("progress", None))
            await graph_finished.wait()

        graph_task = asyncio.create_task(run_graph())
        poll_task = asyncio.create_task(poll_blackboard())

        try:
            while not graph_finished.is_set() or not event_queue.empty():
                try:
                    event_kind, node_name = await asyncio.wait_for(event_queue.get(), timeout=0.45)
                except asyncio.TimeoutError:
                    continue

                current_board = load_blackboard(project_id) or blackboard
                yield build_stream_snapshot(current_board, event_kind, stage_name, node_name)

            await graph_task
            if graph_error is not None:
                raise graph_error

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
            if not graph_task.done():
                graph_task.cancel()
                try:
                    await graph_task
                except asyncio.CancelledError:
                    pass

    async def resume_stage(
        self,
        stage_name: str,
        project_id: str,
    ) -> ProjectBlackboard:
        graph = self._stage_graphs[stage_name]
        result: WorkflowState = await graph.ainvoke(
            None,
            config=self._run_config(project_id),
        )
        updated = result["blackboard"]
        save_blackboard(updated)
        return updated

    async def analyse_reference(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_ANALYSE_REFERENCE, blackboard)

    async def research_topic(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_RESEARCH_TOPIC, blackboard)

    async def discover_candidates(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_DISCOVER_CANDIDATES, blackboard)

    async def discover_and_analyse_candidates(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self.discover_candidates(blackboard)

    async def select_ranking(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self._invoke_stage(STAGE_SELECT_RANKING, blackboard)

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
        blackboard.waiting_for_human = False
        blackboard.human_gate_type = None
        save_blackboard(blackboard)
        return blackboard

    async def resume_after_human_gate(self, project_id: str, stage_name: str) -> ProjectBlackboard:
        return await self.resume_stage(stage_name, project_id)

    @property
    def full_pipeline_graph(self) -> CompiledStateGraph:
        return self._full_pipeline_graph
