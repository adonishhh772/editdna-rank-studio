import json
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi.responses import StreamingResponse

from app.agents.workflow.runner import LangGraphRunner
from app.blackboard import ProjectBlackboard


async def workflow_event_generator(
    runner: LangGraphRunner,
    stage_name: str,
    blackboard: ProjectBlackboard,
) -> AsyncIterator[str]:
    try:
        async for event in runner.stream_stage(stage_name, blackboard):
            yield f"data: {json.dumps(event, default=str)}\n\n"
    except Exception as exc:
        error_payload = {"type": "error", "detail": str(exc), "stage": stage_name}
        yield f"data: {json.dumps(error_payload)}\n\n"


def workflow_streaming_response(
    runner: LangGraphRunner,
    stage_name: str,
    blackboard: ProjectBlackboard,
) -> StreamingResponse:
    return StreamingResponse(
        workflow_event_generator(runner, stage_name, blackboard),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def run_stage_or_stream(
    stream: bool,
    runner: LangGraphRunner,
    stage_name: str,
    blackboard: ProjectBlackboard,
    invoke: Callable[[], Awaitable[ProjectBlackboard]],
) -> StreamingResponse | ProjectBlackboard:
    if stream:
        return workflow_streaming_response(runner, stage_name, blackboard)
    return await invoke()
