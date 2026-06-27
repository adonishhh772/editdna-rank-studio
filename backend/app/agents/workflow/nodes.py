import asyncio
from collections.abc import Callable
from typing import Any

from app.agents.base import BaseAgent
from app.agents.candidate_analysis_agent import CandidateAnalysisAgent
from app.agents.candidate_discovery_agent import CandidateDiscoveryAgent
from app.agents.comparison_agent import ComparisonAgent
from app.agents.fusion_agent import FusionAgent
from app.agents.human_gate_agent import HumanGateAgent
from app.agents.moe_bus import MoEBus
from app.agents.mubit_memory_agent import MubitMemoryAgent
from app.agents.platform_video_download_agent import PlatformVideoDownloadAgent
from app.agents.platform_video_search_agent import PlatformVideoSearchAgent
from app.agents.ranking_agent import RankingAgent
from app.agents.reference_analyst_agent import ReferenceAnalystAgent
from app.agents.slng_audio_agent import SLNGAudioAgent
from app.agents.story_agent import CaptionAgent, CriticAgent, CutAgent, MotionAgent, StoryAgent
from app.agents.tavily_research_agent import TavilyResearchAgent
from app.agents.topic_agent import TopicAgent
from app.agents.workflow.state import WorkflowState
from app.blackboard import ProjectBlackboard
from app.config import get_settings
from app.db import new_id, save_blackboard
from app.schemas import EditPlan, FeedbackEvent, RankedClip
from app.constants.harness import HARNESS_ROUTE_CONTINUE, HARNESS_ROUTE_RETRY, MAX_HARNESS_REVISIONS
from app.services.goal_harness import reset_moe_state_for_retry
from app.services.renderer import VideoRenderer
from app.services.story_coherence_service import (
    enrich_ranked_clip_story_fields,
    evaluate_edit_plan_story_coherence,
)
from app.services.video_analysis_store import build_edit_video_insights

MAX_AGENT_RETRIES = 2


async def run_agent_with_retry(
    agent: BaseAgent,
    blackboard: ProjectBlackboard,
) -> ProjectBlackboard:
    last_error: Exception | None = None
    for attempt in range(MAX_AGENT_RETRIES + 1):
        try:
            return await agent.execute(blackboard)
        except Exception as exc:
            last_error = exc
            if attempt >= MAX_AGENT_RETRIES:
                raise
            await asyncio.sleep(1.5 * (attempt + 1))
    if last_error:
        raise last_error
    return blackboard


def make_agent_node(agent_factory: Callable[[], BaseAgent]) -> Callable[[WorkflowState], Any]:
    async def node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
        blackboard = await run_agent_with_retry(agent_factory(), state["blackboard"])
        save_blackboard(blackboard)
        return {"blackboard": blackboard}

    return node


def apply_fusion_to_sections(
    blackboard: ProjectBlackboard,
    candidates: list,
    avg_duration: float,
) -> tuple[str, str, list[RankedClip], list[dict], list[dict], list[dict]]:
    fusion = blackboard.moe_fusion
    hook_text = fusion.hook_text if fusion else f"Top {len(candidates)} {blackboard.topic or 'Picks'}"
    outro_text = fusion.outro_text if fusion else "Which one wins for you?"

    clip_by_rank = {item["rank"]: item for item in (fusion.clip_adjustments if fusion else [])}
    caption_by_rank = {item["rank"]: item for item in (fusion.caption_updates if fusion else [])}
    motion_by_rank = {item["rank"]: item for item in (fusion.motion_updates if fusion else [])}
    transition_by_rank = {item["rank"]: item for item in (fusion.transition_updates if fusion else [])}

    sections: list[RankedClip] = []
    captions: list[dict] = []
    motion_plan: list[dict] = []
    transition_plan: list[dict] = []

    for candidate in sorted(candidates, key=lambda item: item.recommended_rank or 99):
        rank = candidate.recommended_rank or len(sections) + 1
        duration = candidate.duration_sec or avg_duration
        clip = clip_by_rank.get(rank, {})
        caption = caption_by_rank.get(rank, {})
        motion = motion_by_rank.get(rank, {})
        transition = transition_by_rank.get(rank, {})

        clip_start = float(clip.get("clip_start_sec", candidate.clip_start_sec or 0.0))
        default_end = candidate.clip_end_sec or min(duration, avg_duration + 1.0)
        clip_end = float(clip.get("clip_end_sec", default_end))
        clip_end = max(clip_end, clip_start + 1.0)

        label_text = str(caption.get("label_text", candidate.concept[:60]))
        caption_text = str(caption.get("caption_text", candidate.concept[:80]))
        voiceover_text = str(caption.get("voiceover_text", f"Number {rank}: {candidate.concept}"))

        section_reason = candidate.highlight_reason or candidate.reason
        analysis_scores = {
            "topic_match": candidate.topic_match_score,
            "visual_quality": candidate.visual_quality_score,
            "audio_quality": candidate.audio_quality_score,
            "motion_energy": candidate.motion_energy_score,
            "text_relevance": candidate.text_relevance_score,
            "reference_style_fit": candidate.reference_style_fit_score,
            "overall": candidate.overall_score,
        }

        sections.append(
            RankedClip(
                rank=rank,
                candidate_id=candidate.candidate_id,
                title=candidate.title,
                source_file_path=candidate.local_file_path or "",
                clip_start_sec=clip_start,
                clip_end_sec=clip_end,
                label_text=label_text,
                voiceover_text=voiceover_text,
                caption_text=caption_text,
                reason=section_reason,
                highlight_reason=candidate.highlight_reason,
                analysis_scores=analysis_scores,
            )
        )
        sections[-1] = enrich_ranked_clip_story_fields(sections[-1], candidate)
        captions.append({"text": caption_text, "rank": rank})
        motion_plan.append(
            {
                "rank": rank,
                "zoom": bool(motion.get("zoom", rank == 1)),
                "pan": bool(motion.get("pan", False)),
                "scale": float(motion.get("scale", 1.0)),
            }
        )
        transition_plan.append({"type": str(transition.get("type", "hard_cut")), "rank": rank})

    return hook_text, outro_text, sections, captions, motion_plan, transition_plan


async def validate_gemini_key_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    get_settings().require_key("GEMINI_API_KEY")
    return {"blackboard": state["blackboard"]}


async def validate_tavily_key_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    get_settings().require_key("TAVILY_API_KEY")
    return {"blackboard": state["blackboard"]}


async def validate_candidates_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    blackboard = state["blackboard"]
    candidates = blackboard.approved_candidates or blackboard.selected_candidates
    if not candidates:
        raise RuntimeError("No candidates available for edit plan")
    blackboard.harness_revision_count = 0
    blackboard.harness_goals_met = True
    blackboard.harness_goal_results = []
    save_blackboard(blackboard)
    return {"blackboard": blackboard}


async def moe_pipeline_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    blackboard = state["blackboard"]
    moe_experts = [StoryAgent(), CutAgent(), CaptionAgent(), MotionAgent()]
    moe_bus = MoEBus()
    blackboard = await moe_bus.run_moe_pipeline(moe_experts, blackboard)
    save_blackboard(blackboard)
    return {"blackboard": blackboard}


async def build_edit_plan_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    blackboard = state["blackboard"]
    candidates = blackboard.approved_candidates or blackboard.selected_candidates
    if not candidates:
        raise RuntimeError("No candidates available for edit plan")

    blueprint = blackboard.reference_blueprint
    avg_duration = blueprint.average_item_duration_sec if blueprint else 4.0

    hook_text, outro_text, sections, captions, motion_plan, transition_plan = apply_fusion_to_sections(
        blackboard,
        candidates,
        avg_duration,
    )

    video_insights = build_edit_video_insights(blackboard)
    story_ready, story_issues = evaluate_edit_plan_story_coherence(sections)

    edit_plan = EditPlan(
        edit_plan_id=new_id("plan"),
        project_id=blackboard.project_id,
        version=blackboard.current_version,
        topic=blackboard.topic or "",
        output_aspect_ratio=blueprint.aspect_ratio if blueprint else "9:16",
        output_duration_sec=sum(section.clip_end_sec - section.clip_start_sec for section in sections),
        hook_text=hook_text,
        outro_text=outro_text,
        sections=sections,
        captions=captions,
        audio_plan={"mix": "voice_first", "normalize": True},
        motion_plan=motion_plan,
        transition_plan=transition_plan,
        render_settings={"width": 1080, "height": 1920, "fps": 30},
        reference_blueprint_applied=blueprint.model_dump() if blueprint else {},
        memory_influence={
            **blackboard.memory_context,
            "moe_fusion": blackboard.moe_fusion.model_dump() if blackboard.moe_fusion else {},
            "moe_routing": blackboard.moe_routing.model_dump() if blackboard.moe_routing else {},
        },
        video_insights=video_insights,
        story_ready=story_ready,
        story_issues=story_issues,
        needs_human_approval=True,
    )
    blackboard.edit_plan = edit_plan
    save_blackboard(blackboard)
    return {"blackboard": blackboard}


async def render_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    blackboard = state["blackboard"]
    if not blackboard.edit_plan:
        raise RuntimeError("Edit plan is required for rendering")

    renderer = VideoRenderer()
    voiceover = blackboard.edit_plan.audio_plan.get("voiceover_path")
    output_path = await renderer.render(blackboard.edit_plan, voiceover)
    blackboard.output_video_path = output_path
    blackboard.stage = "rendered"
    save_blackboard(blackboard)
    return {"blackboard": blackboard}


async def prepare_regenerate_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    blackboard = state["blackboard"]
    blackboard.current_version += 1
    blackboard.waiting_for_human = False
    blackboard.human_gate_type = None
    blackboard.agent_messages = []
    blackboard.expert_proposals = []
    blackboard.moe_routing = None
    blackboard.moe_fusion = None
    blackboard.harness_revision_count = 0
    blackboard.harness_goals_met = True
    blackboard.harness_goal_results = []

    memory_agent = MubitMemoryAgent()
    blackboard = await memory_agent.recall_context(blackboard)

    latest_feedback = blackboard.feedback_events[-1].feedback_text if blackboard.feedback_events else ""
    if latest_feedback:
        lowered = latest_feedback.lower()
        if "dramatic" in lowered and ("#1" in lowered or "number 1" in lowered):
            for candidate in blackboard.approved_candidates or blackboard.selected_candidates:
                if candidate.recommended_rank == 1:
                    candidate.motion_energy_score = min(candidate.motion_energy_score + 0.2, 1.0)
        if "faster" in lowered and blackboard.edit_plan:
            for section in blackboard.edit_plan.sections:
                section.clip_end_sec = max(section.clip_start_sec + 1.5, section.clip_end_sec - 0.5)
        if "slower" in lowered and blackboard.edit_plan:
            for section in blackboard.edit_plan.sections:
                section.clip_end_sec += 0.5

    save_blackboard(blackboard)
    return {"blackboard": blackboard}


async def feedback_memory_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    blackboard = state["blackboard"]
    memory_agent = MubitMemoryAgent()
    blackboard = await memory_agent.write_feedback_memory(blackboard)
    save_blackboard(blackboard)
    return {"blackboard": blackboard}


async def prepare_harness_retry_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    blackboard = state["blackboard"]
    blackboard.harness_revision_count += 1
    blackboard = reset_moe_state_for_retry(blackboard)
    save_blackboard(blackboard)
    return {"blackboard": blackboard}


def route_after_critic(state: WorkflowState) -> str:
    blackboard = state["blackboard"]
    if (
        not blackboard.harness_goals_met
        and blackboard.harness_revision_count < MAX_HARNESS_REVISIONS
    ):
        return HARNESS_ROUTE_RETRY
    return HARNESS_ROUTE_CONTINUE


async def finalize_edit_plan_node(state: WorkflowState) -> dict[str, ProjectBlackboard]:
    blackboard = state["blackboard"]
    blackboard.stage = "edit_plan_ready"
    save_blackboard(blackboard)
    return {"blackboard": blackboard}


reference_analyst_node = make_agent_node(ReferenceAnalystAgent)
topic_node = make_agent_node(TopicAgent)
memory_recall_node = make_agent_node(MubitMemoryAgent)
tavily_research_node = make_agent_node(TavilyResearchAgent)
candidate_discovery_node = make_agent_node(CandidateDiscoveryAgent)
platform_video_search_node = make_agent_node(PlatformVideoSearchAgent)
platform_video_download_pool_node = make_agent_node(lambda: PlatformVideoDownloadAgent(target="pool"))
candidate_analysis_node = make_agent_node(CandidateAnalysisAgent)
ranking_node = make_agent_node(RankingAgent)
candidate_approval_gate_node = make_agent_node(lambda: HumanGateAgent("candidate_approval"))
platform_video_download_approved_node = make_agent_node(lambda: PlatformVideoDownloadAgent(target="approved"))
fusion_node = make_agent_node(FusionAgent)
slng_audio_node = make_agent_node(SLNGAudioAgent)
critic_node = make_agent_node(CriticAgent)
edit_plan_approval_gate_node = make_agent_node(lambda: HumanGateAgent("edit_plan_approval"))
comparison_node = make_agent_node(ComparisonAgent)
