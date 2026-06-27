from typing import Any

from app.blackboard import ProjectBlackboard
from app.schemas import AgentTrace
from app.services.preference_learning_service import summarize_preferences_for_ui
from app.constants.workflow import (
    NODE_BUILD_EDIT_PLAN,
    NODE_CANDIDATE_ANALYSIS,
    NODE_CANDIDATE_APPROVAL_GATE,
    NODE_CANDIDATE_DISCOVERY,
    NODE_COMPARISON,
    NODE_CRITIC,
    NODE_EDIT_PLAN_APPROVAL_GATE,
    NODE_FEEDBACK_MEMORY,
    NODE_FUSION,
    NODE_MEMORY_RECALL,
    NODE_MOE_PIPELINE,
    NODE_PLATFORM_VIDEO_DOWNLOAD_APPROVED,
    NODE_PLATFORM_VIDEO_DOWNLOAD_POOL,
    NODE_PLATFORM_VIDEO_SEARCH,
    NODE_PREPARE_REGENERATE,
    NODE_PREPARE_HARNESS_RETRY,
    NODE_RANKING,
    NODE_REFERENCE_ANALYST,
    NODE_RENDER,
    NODE_SLNG_AUDIO,
    NODE_TAVILY_RESEARCH,
    NODE_TOPIC,
)

NODE_DISPLAY_LABELS: dict[str, str] = {
    "validate_gemini": "Checking Gemini key",
    "validate_tavily": "Checking Tavily key",
    "validate_candidates": "Checking candidates",
    NODE_REFERENCE_ANALYST: "Analyzing reference video",
    "reference_video_probe": "Probing reference format",
    "reference_structure_analysis": "Analysing structure & pacing",
    "reference_audio_analysis": "Analysing audio style",
    "reference_blueprint_memory": "Writing reference DNA to memory",
    "candidate_analysis_swarm": "Analysing candidate video",
    "candidate_visual_analysis": "Scoring visual & topic fit",
    "candidate_segment_analysis": "Selecting highlight segment",
    "candidate_preview": "Generating preview thumbnail",
    NODE_TOPIC: "Extracting topic",
    NODE_MEMORY_RECALL: "Loading memory",
    NODE_TAVILY_RESEARCH: "Researching topic",
    "reference_format_detection": "Detecting Shorts vs video",
    "tavily_topic_search": "Searching web for concepts",
    "tavily_deep_research": "Running deep research",
    "platform_search_swarm": "Searching YouTube + TikTok",
    "youtube_shorts_search": "Searching YouTube Shorts",
    "tiktok_search": "Searching TikTok clips",
    "preference_auto_select": "Auto-selecting from learned preferences",
    NODE_CANDIDATE_DISCOVERY: "Building candidate list",
    NODE_PLATFORM_VIDEO_SEARCH: "Finding video URLs",
    NODE_CANDIDATE_ANALYSIS: "Scoring candidates",
    NODE_RANKING: "Ranking top picks",
    NODE_CANDIDATE_APPROVAL_GATE: "Waiting for approval",
    NODE_PLATFORM_VIDEO_DOWNLOAD_APPROVED: "Skipping bulk download",
    NODE_MOE_PIPELINE: "Running edit expert swarm",
    "moe_edit_swarm": "Coordinating Story, Cut, Caption, Motion experts",
    NODE_FUSION: "Merging expert plans",
    NODE_BUILD_EDIT_PLAN: "Building edit plan",
    NODE_SLNG_AUDIO: "Generating voiceover",
    NODE_CRITIC: "Reviewing edit plan goals",
    NODE_PREPARE_HARNESS_RETRY: "Retrying toward goals",
    NODE_EDIT_PLAN_APPROVAL_GATE: "Waiting for edit approval",
    "finalize_edit_plan": "Finalizing plan",
    NODE_RENDER: "Rendering video",
    "render_swarm": "Coordinating video render swarm",
    "rank_clip_render": "Rendering rank clip",
    "video_stitch": "Stitching rank clips",
    "hook_overlay": "Adding hook overlay",
    "audio_mix": "Mixing final audio",
    NODE_COMPARISON: "Comparing output",
    NODE_PREPARE_REGENERATE: "Preparing rerun",
    NODE_FEEDBACK_MEMORY: "Saving feedback",
}


def node_display_label(node_name: str | None) -> str | None:
    if node_name is None:
        return None
    return NODE_DISPLAY_LABELS.get(node_name, node_name.replace("_", " "))


def find_running_trace(blackboard: ProjectBlackboard) -> dict[str, Any] | None:
    for trace in reversed(blackboard.traces):
        if trace.status == "running":
            return trace.model_dump()
    return None


def trace_activity_text(trace: AgentTrace) -> str | None:
    if trace.visible_reasoning and trace.visible_reasoning.strip():
        return trace.visible_reasoning.strip()
    if trace.output_summary and trace.output_summary.strip():
        return trace.output_summary.strip()
    if trace.input_summary and trace.input_summary.strip():
        return trace.input_summary.strip()
    return None


def blackboard_activity_signature(blackboard: ProjectBlackboard) -> tuple[Any, ...]:
    trace_signature = tuple(
        (
            trace.trace_id,
            trace.status,
            trace.visible_reasoning or "",
            trace.output_summary or "",
            len(trace.tool_calls),
        )
        for trace in blackboard.traces
    )
    return (
        trace_signature,
        len(blackboard.download_events),
        len(blackboard.agent_messages),
        blackboard.stage,
        len(blackboard.memory_updates),
        tuple(sorted(blackboard.memory_context.keys())),
    )


def enrich_stream_snapshot(snapshot: dict[str, Any], blackboard: ProjectBlackboard) -> dict[str, Any]:
    snapshot["memory_context"] = blackboard.memory_context
    snapshot["memory_updates"] = [update for update in blackboard.memory_updates]
    snapshot["learning_preferences"] = summarize_preferences_for_ui(blackboard.memory_context)
    return snapshot


def build_stream_snapshot(
    blackboard: ProjectBlackboard,
    event_type: str,
    stage_name: str,
    node_name: str | None = None,
) -> dict[str, Any]:
    running_trace = find_running_trace(blackboard)
    active_reasoning: str | None = None
    if running_trace is not None:
        active_reasoning = trace_activity_text(AgentTrace.model_validate(running_trace))

    snapshot = {
        "type": event_type,
        "stage": stage_name,
        "node": node_name,
        "node_label": node_display_label(node_name),
        "traces": [trace.model_dump() for trace in blackboard.traces],
        "download_events": [event.model_dump() for event in blackboard.download_events],
        "agent_messages": [message.model_dump() for message in blackboard.agent_messages],
        "running_trace": running_trace,
        "active_reasoning": active_reasoning,
    }
    return enrich_stream_snapshot(snapshot, blackboard)
