from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from app.agents.orchestrator import LangGraphRunner
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
from app.routes.review_streaming import run_review_or_stream
from app.routes.workflow_streaming import run_stage_or_stream
from app.services.preference_learning_service import summarize_preferences_for_ui
from app.config import get_settings
from app.constants.video_sources import validate_reference_video_url
from app.db import delete_project, list_projects, load_blackboard, new_id, save_blackboard, utc_now
from app.schemas import (
    ApiStatusResponse,
    CandidateApprovalRequest,
    CandidateReorderRequest,
    CandidateReviewStatusResponse,
    FeedbackEvent,
    ProjectCreateRequest,
    ProjectSummaryResponse,
    ReferenceVideoUrlRequest,
    TextFeedbackRequest,
    TopicRequest,
)
from app.services.approval_service import ApprovalService
from app.services.asset_store import AssetStore
from app.services.reference_media_service import ensure_reference_local_path

router = APIRouter(prefix="/api/projects", tags=["projects"])
orchestrator: LangGraphRunner | None = None
approval_service = ApprovalService()
asset_store = AssetStore()


def get_board(project_id: str):
    board = load_blackboard(project_id)
    if board is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return board


def get_orchestrator() -> LangGraphRunner:
    if orchestrator is None:
        return LangGraphRunner()
    return orchestrator


@router.get("/status/integrations")
async def integration_status() -> ApiStatusResponse:
    settings = get_settings()
    missing = settings.missing_keys()
    return ApiStatusResponse(
        gemini=bool(settings.gemini_api_key),
        tavily=bool(settings.tavily_api_key),
        slng=bool(settings.slng_api_key),
        mubit=bool(settings.mubit_api_key),
        missing_keys=missing,
        allow_demo_fallback=settings.allow_demo_fallback,
    )


@router.post("")
async def create_project(payload: ProjectCreateRequest):
    from app.db import create_project

    board = create_project(payload.user_id, payload.title)
    return board.model_dump()


@router.get("")
async def get_projects(
    user_id: str | None = Query(default=None),
    include_tests: bool = Query(default=False),
) -> list[ProjectSummaryResponse]:
    records = list_projects(include_tests=include_tests)
    if user_id is not None:
        records = [record for record in records if record["user_id"] == user_id]
    records.sort(key=lambda record: record["updated_at"], reverse=True)
    return [ProjectSummaryResponse.model_validate(record) for record in records]


@router.get("/{project_id}")
async def get_project(project_id: str):
    return get_board(project_id).model_dump()


@router.delete("/{project_id}")
async def remove_project(project_id: str):
    board = load_blackboard(project_id)
    if board is None:
        raise HTTPException(status_code=404, detail="Project not found")

    deleted = delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    asset_store.delete_project_assets(project_id)
    return {"project_id": project_id, "deleted": True}


@router.post("/{project_id}/upload-reference")
async def upload_reference(project_id: str, file: UploadFile = File(...)):
    board = get_board(project_id)
    content = await file.read()
    path = asset_store.save_upload(project_id, file.filename or "reference.mp4", content)
    board.reference_video_path = path
    board.reference_video_url = None
    board.stage = "reference_uploaded"
    save_blackboard(board)
    return {"reference_video_path": path}


@router.post("/{project_id}/reference-url")
async def set_reference_url(project_id: str, payload: ReferenceVideoUrlRequest):
    board = get_board(project_id)
    try:
        validated_url = validate_reference_video_url(payload.video_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    board.reference_video_url = validated_url
    board.reference_video_path = None
    board.stage = "reference_uploaded"
    save_blackboard(board)
    return {"reference_video_url": validated_url}


@router.post("/{project_id}/analyse-reference")
async def analyse_reference(project_id: str, stream: bool = Query(default=False)):
    board = get_board(project_id)
    try:
        result = await run_stage_or_stream(
            stream,
            get_orchestrator(),
            STAGE_ANALYSE_REFERENCE,
            board,
            lambda: get_orchestrator().analyse_reference(board),
        )
        if isinstance(result, StreamingResponse):
            return result
        return result.model_dump()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/topic")
async def set_topic(project_id: str, payload: TopicRequest):
    board = get_board(project_id)
    board.topic = payload.topic
    board.target_platform = payload.target_platform
    save_blackboard(board)
    return board.model_dump()


@router.post("/{project_id}/research")
async def research_topic(project_id: str, stream: bool = Query(default=False)):
    board = get_board(project_id)
    try:
        result = await run_stage_or_stream(
            stream,
            get_orchestrator(),
            STAGE_RESEARCH_TOPIC,
            board,
            lambda: get_orchestrator().research_topic(board),
        )
        if isinstance(result, StreamingResponse):
            return result
        return result.model_dump()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/candidates/discover")
async def discover_candidates(project_id: str, stream: bool = Query(default=False)):
    board = get_board(project_id)
    try:
        result = await run_stage_or_stream(
            stream,
            get_orchestrator(),
            STAGE_DISCOVER_CANDIDATES,
            board,
            lambda: get_orchestrator().discover_candidates(board),
        )
        if isinstance(result, StreamingResponse):
            return result
        return result.model_dump()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/candidates/review/start")
async def start_candidate_review(project_id: str, stream: bool = Query(default=False)):
    board = get_board(project_id)
    try:
        result = await run_review_or_stream(
            stream,
            project_id,
            "candidate_review",
            board,
            approval_service.start_candidate_review,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(result, StreamingResponse):
        return result
    return result.model_dump()


@router.post("/{project_id}/candidates/review/skip")
async def skip_candidate_review_slot(project_id: str, stream: bool = Query(default=False)):
    board = get_board(project_id)
    try:
        result = await run_review_or_stream(
            stream,
            project_id,
            "candidate_review",
            board,
            approval_service.skip_current_slot,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(result, StreamingResponse):
        return result
    return result.model_dump()


@router.get("/{project_id}/candidates/review/status")
async def candidate_review_status(project_id: str) -> CandidateReviewStatusResponse:
    board = get_board(project_id)
    return approval_service.get_review_status(board)


@router.post("/{project_id}/candidates/analyse")
async def analyse_candidates(project_id: str):
    board = get_board(project_id)
    try:
        board = await get_orchestrator().discover_and_analyse_candidates(board)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return board.model_dump()


@router.post("/{project_id}/ranking/select")
async def select_ranking(project_id: str, stream: bool = Query(default=False)):
    board = get_board(project_id)
    result = await run_stage_or_stream(
        stream,
        get_orchestrator(),
        STAGE_SELECT_RANKING,
        board,
        lambda: get_orchestrator().select_ranking(board),
    )
    if isinstance(result, StreamingResponse):
        return result
    return result.model_dump()


@router.get("/{project_id}/candidates")
async def list_candidates(project_id: str):
    board = get_board(project_id)
    return {
        "candidate_pool": [item.model_dump() for item in board.candidate_pool],
        "selected_candidates": [item.model_dump() for item in board.selected_candidates],
        "approved_candidates": [item.model_dump() for item in board.approved_candidates],
    }


@router.post("/{project_id}/candidates/{candidate_id}/approve")
async def approve_candidate(
    project_id: str,
    candidate_id: str,
    payload: CandidateApprovalRequest = CandidateApprovalRequest(),
    stream: bool = Query(default=False),
):
    board = get_board(project_id)
    try:
        result = await run_review_or_stream(
            stream,
            project_id,
            "candidate_review",
            board,
            lambda current_board: approval_service.approve_candidate(current_board, candidate_id),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(result, StreamingResponse):
        return result
    return result.model_dump()


@router.post("/{project_id}/candidates/{candidate_id}/reject")
async def reject_candidate(
    project_id: str,
    candidate_id: str,
    payload: CandidateApprovalRequest = CandidateApprovalRequest(),
    stream: bool = Query(default=False),
):
    board = get_board(project_id)
    try:
        result = await run_review_or_stream(
            stream,
            project_id,
            "candidate_review",
            board,
            lambda current_board: approval_service.reject_candidate(current_board, candidate_id),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(result, StreamingResponse):
        return result
    return result.model_dump()


@router.post("/{project_id}/candidates/reorder")
async def reorder_candidates(project_id: str, payload: CandidateReorderRequest):
    board = get_board(project_id)
    board = await approval_service.reorder_candidates(board, payload.candidate_ids)
    return board.model_dump()


@router.post("/{project_id}/edit-plan")
async def create_edit_plan(project_id: str, stream: bool = Query(default=False)):
    board = get_board(project_id)
    if not board.approved_candidates:
        board.approved_candidates = [
            item for item in board.selected_candidates if item.status != "rejected"
        ]
    result = await run_stage_or_stream(
        stream,
        get_orchestrator(),
        STAGE_CREATE_EDIT_PLAN,
        board,
        lambda: get_orchestrator().create_edit_plan(board),
    )
    if isinstance(result, StreamingResponse):
        return result
    return result.model_dump()


@router.post("/{project_id}/edit-plan/approve")
async def approve_edit_plan(project_id: str):
    board = get_board(project_id)
    if not board.edit_plan:
        raise HTTPException(status_code=400, detail="Edit plan is not ready for approval")
    should_resume = board.human_gate_type == "edit_plan_approval"
    board = await get_orchestrator().clear_human_gate(board)
    if board.edit_plan:
        board.edit_plan.needs_human_approval = False
    board.stage = "edit_plan_approved"
    save_blackboard(board)
    if should_resume:
        board = await get_orchestrator().resume_after_human_gate(project_id, STAGE_CREATE_EDIT_PLAN)
    return board.model_dump()


@router.post("/{project_id}/render")
async def render_video(project_id: str, stream: bool = Query(default=False)):
    board = get_board(project_id)
    result = await run_stage_or_stream(
        stream,
        get_orchestrator(),
        STAGE_RENDER,
        board,
        lambda: get_orchestrator().render(board),
    )
    if isinstance(result, StreamingResponse):
        return result
    return result.model_dump()


@router.post("/{project_id}/feedback/text")
async def text_feedback(project_id: str, payload: TextFeedbackRequest):
    board = get_board(project_id)
    feedback = FeedbackEvent(
        feedback_id=new_id("fb"),
        project_id=project_id,
        run_id=board.run_id,
        user_id=payload.user_id,
        feedback_type=payload.feedback_type,
        target_type=payload.target_type,
        target_id=payload.target_id,
        feedback_text=payload.feedback_text,
        created_at=utc_now(),
    )
    board = await get_orchestrator().apply_feedback_and_learn(board, feedback)
    return board.model_dump()


@router.post("/{project_id}/feedback/audio")
async def audio_feedback(project_id: str, file: UploadFile = File(...)):
    board = get_board(project_id)
    content = await file.read()
    audio_path = asset_store.save_upload(project_id, file.filename or "feedback.wav", content)
    try:
        from app.integrations.slng_client import SLNGAudioClient

        slng = SLNGAudioClient()
        transcript = await slng.transcribe_feedback_audio(audio_path)
        command = await slng.parse_voice_command(transcript)
        feedback = FeedbackEvent(
            feedback_id=new_id("fb"),
            project_id=project_id,
            run_id=board.run_id,
            user_id=board.user_id,
            feedback_type="voice_feedback",
            feedback_text=transcript,
            after_state=command,
            created_at=utc_now(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    board = await get_orchestrator().apply_feedback_and_learn(board, feedback)
    return {"blackboard": board.model_dump(), "transcript": feedback.feedback_text, "command": feedback.after_state}


@router.post("/{project_id}/regenerate")
async def regenerate(project_id: str):
    board = get_board(project_id)
    board = await get_orchestrator().regenerate(board)
    return board.model_dump()


@router.post("/{project_id}/final-approve")
async def final_approve(project_id: str):
    board = get_board(project_id)
    feedback = FeedbackEvent(
        feedback_id=new_id("fb"),
        project_id=project_id,
        run_id=board.run_id,
        user_id=board.user_id,
        feedback_type="final_approve",
        feedback_text="Final approve",
        created_at=utc_now(),
    )
    board = await get_orchestrator().apply_feedback_and_learn(board, feedback)
    board = await get_orchestrator().compare(board)
    board.stage = "final_approved"
    save_blackboard(board)
    return board.model_dump()


@router.get("/{project_id}/comparison")
async def get_comparison(project_id: str):
    board = get_board(project_id)
    if board.comparison_report is None:
        board = await get_orchestrator().compare(board)
    return board.comparison_report.model_dump() if board.comparison_report else {}


@router.get("/{project_id}/traces")
async def get_traces(project_id: str):
    board = get_board(project_id)
    return [trace.model_dump() for trace in board.traces]


@router.get("/{project_id}/downloads")
async def get_download_events(project_id: str):
    board = get_board(project_id)
    return [event.model_dump() for event in board.download_events]


@router.get("/{project_id}/memory")
async def get_memory(project_id: str):
    board = get_board(project_id)
    return {
        "memory_context": board.memory_context,
        "memory_updates": board.memory_updates,
        "learning_preferences": summarize_preferences_for_ui(board.memory_context),
    }


@router.get("/{project_id}/media/reference")
async def serve_reference(project_id: str):
    board = get_board(project_id)
    local_path = await ensure_reference_local_path(
        project_id=project_id,
        reference_video_path=board.reference_video_path,
        reference_video_url=board.reference_video_url,
    )
    if local_path:
        if board.reference_video_path != local_path:
            board.reference_video_path = local_path
            save_blackboard(board)
        return FileResponse(local_path)
    if board.reference_video_url:
        return RedirectResponse(url=board.reference_video_url)
    raise HTTPException(status_code=404, detail="Reference video not found")


@router.get("/{project_id}/media/output")
async def serve_output(project_id: str):
    board = get_board(project_id)
    if not board.output_video_path:
        raise HTTPException(status_code=404, detail="Output video not found")
    return FileResponse(board.output_video_path)
