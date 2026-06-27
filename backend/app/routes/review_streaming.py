import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi.responses import StreamingResponse

from app.agents.workflow.stream_events import (
    blackboard_activity_signature,
    build_stream_snapshot,
)
from app.blackboard import ProjectBlackboard
from app.db import load_blackboard, save_blackboard


async def review_event_generator(
    project_id: str,
    stage_name: str,
    blackboard: ProjectBlackboard,
    operation: Callable[[ProjectBlackboard], Awaitable[ProjectBlackboard]],
) -> AsyncIterator[str]:
    finished = asyncio.Event()
    operation_error: Exception | None = None

    async def run_operation() -> None:
        nonlocal operation_error
        try:
            result = await operation(blackboard)
            save_blackboard(result)
        except Exception as exc:
            operation_error = exc
        finally:
            finished.set()

    task = asyncio.create_task(run_operation())
    current_board = load_blackboard(project_id) or blackboard
    last_signature = blackboard_activity_signature(current_board)

    try:
        while not finished.is_set():
            await asyncio.sleep(0.35)
            polled_board = load_blackboard(project_id)
            if polled_board is None:
                continue
            signature = blackboard_activity_signature(polled_board)
            if signature != last_signature:
                last_signature = signature
                snapshot = build_stream_snapshot(polled_board, "progress", stage_name)
                yield f"data: {json.dumps(snapshot, default=str)}\n\n"

        await task
        if operation_error is not None:
            error_payload = {"type": "error", "detail": str(operation_error), "stage": stage_name}
            yield f"data: {json.dumps(error_payload)}\n\n"
            return

        final_board = load_blackboard(project_id) or blackboard
        complete_event = build_stream_snapshot(final_board, "complete", stage_name)
        complete_event["blackboard"] = final_board.model_dump()
        yield f"data: {json.dumps(complete_event, default=str)}\n\n"
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


def review_streaming_response(
    project_id: str,
    stage_name: str,
    blackboard: ProjectBlackboard,
    operation: Callable[[ProjectBlackboard], Awaitable[ProjectBlackboard]],
) -> StreamingResponse:
    return StreamingResponse(
        review_event_generator(project_id, stage_name, blackboard, operation),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def run_review_or_stream(
    stream: bool,
    project_id: str,
    stage_name: str,
    blackboard: ProjectBlackboard,
    operation: Callable[[ProjectBlackboard], Awaitable[ProjectBlackboard]],
) -> StreamingResponse | ProjectBlackboard:
    if stream:
        return review_streaming_response(project_id, stage_name, blackboard, operation)
    result = await operation(blackboard)
    save_blackboard(result)
    return result
