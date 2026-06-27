import asyncio
import shutil
from pathlib import Path
from typing import Any

from app.blackboard import ProjectBlackboard
from app.config import get_settings
from app.constants.demo import (
    DEMO_AGENT_CANDIDATE_PREVIEW,
    DEMO_AGENT_CANDIDATE_SEGMENT,
    DEMO_AGENT_CANDIDATE_VISUAL_ANALYSIS,
    DEMO_AGENT_PLATFORM_VIDEO_DOWNLOAD,
    DEMO_AGENT_PLATFORM_VIDEO_SEARCH,
    DEMO_ANALYSIS_SOURCE,
    DEMO_CANDIDATE_STEP_DELAY_SEC,
    DEMO_RENDER_TOTAL_SEC,
    DEMO_STEP_DELAY_SEC,
)
from app.db import new_id, save_blackboard, utc_now
from app.schemas import (
    AgentMessage,
    AgentTrace,
    AiFeedbackSuggestion,
    CandidateReviewSlot,
    CandidateVideo,
    ComparisonReport,
    DownloadEvent,
    ExpertProposal,
    MemoryUpdate,
    MoEFusionResult,
    MoERoutingWeights,
    ReferenceBlueprint,
    ReferenceSection,
    TopicResearch,
)
from app.services.demo_pack_loader import DemoPack, get_active_demo_pack
from app.services.segment_selection_service import apply_reference_segment_to_candidate
from app.services.story_coherence_service import enrich_candidate_story_fields
from app.services.video_analysis_store import save_candidate_video_analysis, save_reference_video_analysis
from app.services.video_utils import generate_thumbnail, get_video_duration
from app.agents.workflow import nodes as workflow_nodes
from app.constants.candidate_review import SLOT_STATUS_AWAITING_APPROVAL
from app.constants.render_pipeline import (
    RENDER_STAGE_AUDIO,
    RENDER_STAGE_CAPTION,
    RENDER_STAGE_HOOK,
    RENDER_STAGE_SCALE,
    RENDER_STAGE_STITCH,
    RENDER_STAGE_TRIM,
)
from app.constants.feedback import FEEDBACK_SENTIMENT_POSITIVE, FEEDBACK_TYPE_AI_SUGGESTED
from app.services.feedback_learning_service import (
    build_memory_scope_updates,
    classify_feedback_sentiment,
    feedback_memory_summary,
)


class DemoReplayService:
    def __init__(self, pack: DemoPack) -> None:
        self.pack = pack
        self.settings = get_settings()

    @classmethod
    def active(cls) -> "DemoReplayService":
        return cls(get_active_demo_pack())

    def project_candidates_dir(self, project_id: str) -> Path:
        target_dir = self.settings.upload_dir / project_id / "candidates"
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    async def delay(self, seconds: float = DEMO_STEP_DELAY_SEC) -> None:
        await asyncio.sleep(seconds)

    def _start_trace(
        self,
        blackboard: ProjectBlackboard,
        *,
        agent_id: str,
        agent_name: str,
        input_summary: str,
        visible_reasoning: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentTrace:
        trace = AgentTrace(
            trace_id=new_id("trace"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            agent_id=agent_id,
            agent_name=agent_name,
            status="running",
            input_summary=input_summary,
            visible_reasoning=visible_reasoning,
            started_at=utc_now(),
            metadata=dict(metadata or {}),
        )
        blackboard.traces.append(trace)
        return trace

    def _start_swarm_child_trace(
        self,
        blackboard: ProjectBlackboard,
        *,
        parent_agent_id: str,
        agent_id: str,
        agent_name: str,
        input_summary: str,
        visible_reasoning: str,
    ) -> AgentTrace:
        return self._start_trace(
            blackboard,
            agent_id=agent_id,
            agent_name=agent_name,
            input_summary=input_summary,
            visible_reasoning=visible_reasoning,
            metadata={"parent_agent_id": parent_agent_id, "swarm": True},
        )

    def _append_render_tool_call(
        self,
        trace: AgentTrace,
        *,
        stage: str,
        rank: int | None = None,
        local_file_path: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "tool": "render_pipeline",
            "stage": stage,
            "timestamp": utc_now(),
        }
        if rank is not None:
            payload["rank"] = rank
        if local_file_path is not None:
            payload["local_file_path"] = local_file_path
        trace.tool_calls.append(payload)

    def _complete_trace(
        self,
        trace: AgentTrace,
        *,
        output_summary: str,
        visible_reasoning: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        trace.status = "complete"
        trace.output_summary = output_summary
        if visible_reasoning is not None:
            trace.visible_reasoning = visible_reasoning
        if tool_calls is not None:
            trace.tool_calls = tool_calls
        trace.completed_at = utc_now()

    def _append_download_event(
        self,
        blackboard: ProjectBlackboard,
        *,
        agent_id: str,
        agent_name: str,
        concept: str,
        stage: str,
        candidate_id: str | None = None,
        search_query: str | None = None,
        source_url: str | None = None,
        local_file_path: str | None = None,
        platform: str | None = None,
        file_size_bytes: int | None = None,
    ) -> None:
        blackboard.download_events.append(
            DownloadEvent(
                event_id=new_id("dl"),
                project_id=blackboard.project_id,
                run_id=blackboard.run_id,
                agent_id=agent_id,
                agent_name=agent_name,
                candidate_id=candidate_id,
                concept=concept,
                stage=stage,
                platform=platform,
                search_query=search_query,
                source_url=source_url,
                local_file_path=local_file_path,
                file_size_bytes=file_size_bytes,
                created_at=utc_now(),
            )
        )

    def _append_memory_update(
        self,
        blackboard: ProjectBlackboard,
        *,
        short_term: list[dict[str, str]],
        episodic: list[dict[str, str]] | None = None,
        long_term: list[dict[str, str]] | None = None,
        summary: str,
        confidence: float = 0.9,
    ) -> None:
        blackboard.memory_updates.append(
            MemoryUpdate(
                memory_update_id=new_id("mem"),
                project_id=blackboard.project_id,
                run_id=blackboard.run_id,
                user_id=blackboard.user_id,
                short_term_updates=short_term,
                episodic_updates=episodic or [],
                long_term_updates=long_term or [],
                confidence=confidence,
                summary=summary,
            ).model_dump()
        )

    def _build_reference_blueprint(self, blackboard: ProjectBlackboard) -> ReferenceBlueprint:
        ranking_count = self.pack.ranking_count
        avg_duration = 4.5
        hook_duration = 2.5
        outro_duration = 2.0
        total_duration = hook_duration + (avg_duration * ranking_count) + outro_duration

        sections: list[ReferenceSection] = [
            ReferenceSection(
                name="hook",
                start_sec=0.0,
                end_sec=hook_duration,
                purpose="Hook the viewer with the ranking topic",
                visual_notes="Bold text overlay, fast cuts",
                audio_notes="Upbeat intro music",
                text_notes="Topic title card",
                motion_notes="Quick zoom",
            )
        ]
        cursor = hook_duration
        for rank_number in range(ranking_count, 0, -1):
            end_sec = cursor + avg_duration
            sections.append(
                ReferenceSection(
                    name=f"rank_{rank_number}",
                    rank_number=rank_number,
                    start_sec=cursor,
                    end_sec=end_sec,
                    purpose=f"Reveal rank #{rank_number}",
                    visual_notes="Vertical clip with rank label",
                    audio_notes="Rank sting or voiceover",
                    text_notes=f"Number {rank_number} label",
                    motion_notes="Zoom on rank #1" if rank_number == 1 else "Standard pan",
                )
            )
            cursor = end_sec

        return ReferenceBlueprint(
            blueprint_id=new_id("bp"),
            project_id=blackboard.project_id,
            video_type="ranking_video",
            aspect_ratio="9:16",
            duration_sec=total_duration,
            ranking_count=ranking_count,
            ranking_order="5_to_1" if ranking_count >= 5 else "unknown",
            hook_duration_sec=hook_duration,
            average_item_duration_sec=avg_duration,
            outro_duration_sec=outro_duration,
            section_order=sections,
            caption_style={"font": "bold", "position": "center", "color": "white"},
            text_overlay_style={"style": "rank_label", "animation": "pop_in"},
            transition_style={"type": "hard_cut", "pace": "fast"},
            audio_style={"music": "upbeat", "voiceover": "optional"},
            motion_style={"energy": "high", "zoom_on_rank_one": True},
            pacing_style={"tempo": "fast", "rank_reveal_gap_sec": 0.5},
            hook_style="question_hook",
            rank_reveal_style="countdown",
            final_rank_drama_level="high",
            confidence=0.92,
        )

    def _concept_for_rank(self, rank_number: int) -> str:
        if rank_number in self.pack.rank_concepts:
            return self.pack.rank_concepts[rank_number]
        return f"Rank #{rank_number} pick for {self.pack.topic}"

    def _reject_concept_for_rank(self, rank_number: int, slot_concept: str) -> str:
        if rank_number in self.pack.reject_concepts:
            return self.pack.reject_concepts[rank_number]
        return f"Weak topic match — not strong enough for {slot_concept}"

    def _resolve_reject_source_path(self, rank_number: int) -> Path | None:
        reject_path = self.pack.reject_files.get(rank_number)
        if reject_path is not None and reject_path.exists():
            return reject_path
        if self.pack.reject_fallback_path is not None and self.pack.reject_fallback_path.exists():
            return self.pack.reject_fallback_path
        return None

    def _should_offer_reject_variant(self, slot: CandidateReviewSlot) -> bool:
        if self.pack.reject_demo_slot != slot.slot_rank:
            return False
        if len(slot.rejected_urls) > 0:
            return False
        return self._resolve_reject_source_path(slot.slot_rank) is not None

    def _append_rejection_learning_to_edit_plan(self, blackboard: ProjectBlackboard) -> None:
        if not blackboard.edit_plan or not blackboard.rejected_candidates:
            return

        already_added = any(
            suggestion.source == "demo_rejection_learning"
            for suggestion in blackboard.edit_plan.ai_feedback_suggestions
        )
        if already_added:
            return

        rejected_labels = [
            candidate.concept or candidate.title
            for candidate in blackboard.rejected_candidates
        ]
        learning_summary = (
            "Excluded "
            + ", ".join(rejected_labels[:2])
            + ("…" if len(rejected_labels) > 2 else "")
            + " from the final ranking. Approved clips only appear in the stitched output."
        )
        suggestion = AiFeedbackSuggestion(
            suggestion_id=new_id("suggest"),
            label="Learned from rejection",
            feedback_text=learning_summary,
            severity="info",
            source="demo_rejection_learning",
            rank=blackboard.rejected_candidates[0].recommended_rank,
        )
        blackboard.edit_plan.ai_feedback_suggestions = [
            suggestion,
            *blackboard.edit_plan.ai_feedback_suggestions,
        ]
        blackboard.edit_plan.memory_influence = {
            **blackboard.edit_plan.memory_influence,
            "rejected_candidate_count": len(blackboard.rejected_candidates),
            "rejected_concepts": rejected_labels,
        }

    def _reset_edit_plan_swarm_state(self, blackboard: ProjectBlackboard) -> None:
        blackboard.agent_messages = []
        blackboard.expert_proposals = []
        blackboard.moe_routing = None
        blackboard.moe_fusion = None
        blackboard.harness_revision_count = 0
        blackboard.harness_goals_met = True
        blackboard.harness_goal_results = []

    def _apply_studio_feedback_to_edit_plan(self, blackboard: ProjectBlackboard) -> None:
        if blackboard.edit_plan is None:
            return

        applied_feedback: list[str] = []
        for feedback in blackboard.feedback_events:
            if feedback.feedback_type != FEEDBACK_TYPE_AI_SUGGESTED or not feedback.feedback_text:
                continue
            feedback_text = feedback.feedback_text.strip()
            if not feedback_text:
                continue
            applied_feedback.append(feedback_text)
            lowered = feedback_text.lower()
            if "dramatic" in lowered and ("#1" in lowered or "number 1" in lowered):
                for candidate in blackboard.approved_candidates or blackboard.selected_candidates:
                    if candidate.recommended_rank == 1:
                        candidate.motion_energy_score = min(candidate.motion_energy_score + 0.2, 1.0)
            if "faster" in lowered:
                for section in blackboard.edit_plan.sections:
                    section.clip_end_sec = max(section.clip_start_sec + 1.5, section.clip_end_sec - 0.5)
            if "slower" in lowered:
                for section in blackboard.edit_plan.sections:
                    section.clip_end_sec += 0.5

        if not applied_feedback:
            return

        normalized_applied = {text.strip().lower() for text in applied_feedback}
        blackboard.edit_plan.ai_feedback_suggestions = [
            suggestion
            for suggestion in blackboard.edit_plan.ai_feedback_suggestions
            if suggestion.feedback_text.strip().lower() not in normalized_applied
        ]
        blackboard.edit_plan.story_issues = [
            issue
            for issue in blackboard.edit_plan.story_issues
            if issue.strip().lower() not in normalized_applied
        ]
        blackboard.edit_plan.story_ready = True
        blackboard.edit_plan.memory_influence = {
            **blackboard.edit_plan.memory_influence,
            "applied_studio_feedback": applied_feedback,
        }
        blackboard.edit_plan.hook_text = (
            f"{blackboard.edit_plan.hook_text} — refined from your studio feedback"
        )

    async def _simulate_rank_clip_render(
        self,
        blackboard: ProjectBlackboard,
        *,
        parent_agent_id: str,
        rank_number: int,
        rank_label: str,
        step_delay_sec: float,
    ) -> None:
        rank_trace = self._start_swarm_child_trace(
            blackboard,
            parent_agent_id=parent_agent_id,
            agent_id="rank_clip_render",
            agent_name="Rank Clip Render",
            input_summary=f"Rendering rank #{rank_number}: {rank_label}",
            visible_reasoning=f"Trimming rank #{rank_number} clip window",
        )
        save_blackboard(blackboard)

        micro_stages = [
            (RENDER_STAGE_TRIM, f"Trimming rank #{rank_number} highlight segment"),
            (RENDER_STAGE_SCALE, f"Scaling rank #{rank_number} to 9:16 vertical"),
            (RENDER_STAGE_CAPTION, f"Adding rank #{rank_number} label overlay"),
        ]
        micro_delay_sec = step_delay_sec / len(micro_stages)
        for stage, reasoning in micro_stages:
            rank_trace.visible_reasoning = reasoning
            save_blackboard(blackboard)
            await self.delay(micro_delay_sec)
            self._append_render_tool_call(rank_trace, stage=stage, rank=rank_number)
            save_blackboard(blackboard)

        self._complete_trace(
            rank_trace,
            output_summary=f"Rank #{rank_number} clip ready",
            visible_reasoning=f"Rank #{rank_number} ready for stitch.",
            tool_calls=list(rank_trace.tool_calls),
        )
        save_blackboard(blackboard)

    async def _simulate_render_swarm_stage(
        self,
        blackboard: ProjectBlackboard,
        *,
        parent_agent_id: str,
        agent_id: str,
        agent_name: str,
        input_summary: str,
        visible_reasoning: str,
        output_summary: str,
        render_stage: str,
        step_delay_sec: float,
    ) -> None:
        stage_trace = self._start_swarm_child_trace(
            blackboard,
            parent_agent_id=parent_agent_id,
            agent_id=agent_id,
            agent_name=agent_name,
            input_summary=input_summary,
            visible_reasoning=visible_reasoning,
        )
        save_blackboard(blackboard)
        await self.delay(step_delay_sec)
        self._append_render_tool_call(stage_trace, stage=render_stage)
        self._complete_trace(
            stage_trace,
            output_summary=output_summary,
            visible_reasoning=visible_reasoning,
            tool_calls=list(stage_trace.tool_calls),
        )
        save_blackboard(blackboard)

    async def _simulate_render_pipeline(
        self,
        blackboard: ProjectBlackboard,
        *,
        output_path: Path,
    ) -> None:
        parent_agent_id = "render_swarm"
        approved_candidates = blackboard.approved_candidates or blackboard.selected_candidates
        ranked_candidates = sorted(
            approved_candidates,
            key=lambda candidate: candidate.recommended_rank or 99,
        )
        rank_numbers = [
            candidate.recommended_rank or index + 1
            for index, candidate in enumerate(ranked_candidates)
        ]
        if not rank_numbers:
            rank_numbers = list(range(1, self.pack.ranking_count + 1))

        sections_by_rank: dict[int, str] = {}
        if blackboard.edit_plan is not None:
            for section in blackboard.edit_plan.sections:
                sections_by_rank[section.rank] = (
                    section.video_moment_title or section.label_text or f"Rank #{section.rank}"
                )

        post_render_steps = 3
        total_steps = len(rank_numbers) + post_render_steps
        step_delay_sec = DEMO_RENDER_TOTAL_SEC / total_steps
        sub_agents: list[str] = []

        render_trace = self._start_trace(
            blackboard,
            agent_id=parent_agent_id,
            agent_name="Render Swarm",
            input_summary=f"Render swarm for {len(rank_numbers)} rank clips",
            visible_reasoning="Coordinating rank clip, stitch, hook, and audio sub-agents.",
            metadata={"swarm": True, "clip_count": len(rank_numbers)},
        )
        save_blackboard(blackboard)

        for rank_number in rank_numbers:
            rank_label = sections_by_rank.get(rank_number, f"Rank #{rank_number}")
            await self._simulate_rank_clip_render(
                blackboard,
                parent_agent_id=parent_agent_id,
                rank_number=rank_number,
                rank_label=rank_label,
                step_delay_sec=step_delay_sec,
            )
            sub_agents.append("rank_clip_render")
            render_trace.visible_reasoning = (
                f"Render swarm finished rank #{rank_number} — continuing pipeline."
            )
            save_blackboard(blackboard)

        await self._simulate_render_swarm_stage(
            blackboard,
            parent_agent_id=parent_agent_id,
            agent_id="video_stitch",
            agent_name="Video Stitch",
            input_summary=f"Stitching {len(rank_numbers)} rank clips",
            visible_reasoning="Concatenating ranked clips into one timeline.",
            output_summary="Rank clips stitched",
            render_stage=RENDER_STAGE_STITCH,
            step_delay_sec=step_delay_sec,
        )
        sub_agents.append("video_stitch")

        hook_text = blackboard.edit_plan.hook_text if blackboard.edit_plan else self.pack.topic
        await self._simulate_render_swarm_stage(
            blackboard,
            parent_agent_id=parent_agent_id,
            agent_id="hook_overlay",
            agent_name="Hook Overlay",
            input_summary="Adding opening hook overlay",
            visible_reasoning=f'Applying hook text: "{hook_text[:60]}"',
            output_summary="Hook overlay applied",
            render_stage=RENDER_STAGE_HOOK,
            step_delay_sec=step_delay_sec,
        )
        sub_agents.append("hook_overlay")

        await self._simulate_render_swarm_stage(
            blackboard,
            parent_agent_id=parent_agent_id,
            agent_id="audio_mix",
            agent_name="Audio Mix",
            input_summary="Mixing final audio bed",
            visible_reasoning="Reference-driven mix: balancing clip audio and pacing.",
            output_summary="Final audio mix complete",
            render_stage=RENDER_STAGE_AUDIO,
            step_delay_sec=step_delay_sec,
        )
        sub_agents.append("audio_mix")

        shutil.copy2(self.pack.final_output_path, output_path)
        render_trace.metadata["sub_agents"] = sub_agents
        self._complete_trace(
            render_trace,
            output_summary=f"Video rendered to {output_path.name}",
            visible_reasoning=(
                "Swarm trimmed, scaled, captioned, stitched, and mixed the final ranking video."
            ),
        )
        save_blackboard(blackboard)

    def _build_topic_research(self, blackboard: ProjectBlackboard) -> TopicResearch:
        concepts = [
            self._concept_for_rank(rank_number)
            for rank_number in range(1, self.pack.ranking_count + 1)
        ]
        return TopicResearch(
            project_id=blackboard.project_id,
            topic=blackboard.topic or self.pack.topic,
            ranking_count=self.pack.ranking_count,
            research_summary=(
                f"Demo research for '{self.pack.topic}': identified {self.pack.ranking_count} "
                "strong clip concepts aligned with the reference Shorts format."
            ),
            candidate_concepts=concepts,
            source_urls=[self.pack.youtube_url],
            search_results=[
                {
                    "title": self.pack.topic,
                    "url": self.pack.youtube_url,
                    "score": 0.95,
                }
            ],
            reference_video_format="shorts",
            reference_video_orientation="mobile",
            youtube_search_mode="shorts",
            aspect_ratio_hint="9:16",
            target_candidate_duration_sec=4.5,
            rank_segment_duration_sec=4.0,
            max_source_duration_sec=60.0,
            min_source_duration_sec=2.0,
        )

    def _seed_memory_context(
        self,
        blackboard: ProjectBlackboard,
        *,
        include_topic_preference: bool = False,
    ) -> None:
        blackboard.memory_context.setdefault("demo_mode", True)
        blackboard.memory_context.setdefault("demo_pack_id", self.pack.pack_id)
        if include_topic_preference:
            blackboard.memory_context.setdefault(
                "recalled_preferences",
                {
                    "preferred_format": "shorts",
                    "preferred_orientation": "mobile",
                    "topic": self.pack.topic,
                },
            )

    async def analyse_reference(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.reference_video_url and not blackboard.reference_video_path:
            blackboard.reference_video_url = self.pack.youtube_url

        probe_trace = self._start_trace(
            blackboard,
            agent_id="reference_video_probe",
            agent_name="Reference Video Probe",
            input_summary="Probing reference Shorts format",
            visible_reasoning="Detecting duration, orientation, and platform metadata.",
        )
        save_blackboard(blackboard)
        await self.delay()
        blackboard.memory_context["reference_probe_metadata"] = {
            "duration_sec": 45.0,
            "orientation": "mobile",
            "aspect_ratio": "9:16",
            "platform": "youtube",
            "format": "shorts",
            "source_url": blackboard.reference_video_url or self.pack.youtube_url,
        }
        self._complete_trace(
            probe_trace,
            output_summary="Shorts · 9:16 · mobile",
            visible_reasoning="Reference is a vertical Shorts ranking video.",
        )
        save_blackboard(blackboard)
        await self.delay()

        structure_trace = self._start_trace(
            blackboard,
            agent_id="reference_structure_analysis",
            agent_name="Structure & Pacing Analysis",
            input_summary="Extracting hook, rank flow, and pacing grammar",
            visible_reasoning="Mapping hook timing, rank reveals, and segment pacing.",
        )
        save_blackboard(blackboard)
        await self.delay()

        blueprint = self._build_reference_blueprint(blackboard)
        blackboard.reference_blueprint = blueprint
        save_reference_video_analysis(blackboard)
        self._complete_trace(
            structure_trace,
            output_summary=(
                f"{blueprint.ranking_count} ranks · hook {blueprint.hook_duration_sec}s · "
                f"~{blueprint.average_item_duration_sec}s per item"
            ),
            visible_reasoning="Extracted editing structure: hook, rank order, segment timing, reveal pattern.",
            tool_calls=[{"tool": "demo_reference_structure", "ranking_count": blueprint.ranking_count}],
        )
        save_blackboard(blackboard)
        await self.delay()

        audio_trace = self._start_trace(
            blackboard,
            agent_id="reference_audio_analysis",
            agent_name="Reference Audio Analysis",
            input_summary="Analysing music and voiceover style",
            visible_reasoning="Identifying tempo, energy, and rank sting patterns.",
        )
        save_blackboard(blackboard)
        await self.delay()
        self._complete_trace(
            audio_trace,
            output_summary="Upbeat music · optional voiceover · rank stings",
            visible_reasoning="Audio style captured for edit plan matching.",
        )
        save_blackboard(blackboard)
        await self.delay()

        memory_trace = self._start_trace(
            blackboard,
            agent_id="reference_blueprint_memory",
            agent_name="Reference Blueprint Memory",
            input_summary="Persisting reference editing DNA",
            visible_reasoning="Storing blueprint patterns for candidate matching.",
        )
        save_blackboard(blackboard)
        await self.delay()
        self._append_memory_update(
            blackboard,
            short_term=[
                {
                    "content": "Reference blueprint stored — editing DNA captured from source video",
                    "type": "reference_dna",
                }
            ],
            episodic=[{"content": "Reference video is a vertical Shorts ranking format"}],
            summary="Reference editing DNA saved to memory",
        )
        self._complete_trace(
            memory_trace,
            output_summary="Reference DNA written to project memory",
            visible_reasoning="Blueprint available for candidate scoring and edit planning.",
        )
        blackboard.stage = "reference_analysed"
        save_blackboard(blackboard)
        return blackboard

    async def research_topic(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.topic:
            blackboard.topic = self.pack.topic

        topic_trace = self._start_trace(
            blackboard,
            agent_id="topic_agent",
            agent_name="Topic Agent",
            input_summary=f"Topic: {blackboard.topic}",
            visible_reasoning="Normalizing topic for research and candidate discovery.",
        )
        save_blackboard(blackboard)
        await self.delay()
        self._complete_trace(
            topic_trace,
            output_summary=f"Topic set: {blackboard.topic}",
            visible_reasoning="Ready for Tavily research pass.",
        )
        save_blackboard(blackboard)
        await self.delay()

        recall_trace = self._start_trace(
            blackboard,
            agent_id="mubit_memory",
            agent_name="Mubit Memory Agent",
            input_summary="Recalling user preferences",
            visible_reasoning="Loading Shorts preferences and prior approvals from memory.",
        )
        save_blackboard(blackboard)
        await self.delay()
        self._seed_memory_context(blackboard, include_topic_preference=True)
        self._complete_trace(
            recall_trace,
            output_summary="Recalled memory context",
            visible_reasoning="Prefer vertical Shorts clips with fast pacing.",
        )
        save_blackboard(blackboard)
        await self.delay()

        research_trace = self._start_trace(
            blackboard,
            agent_id="tavily_research",
            agent_name="Tavily Research Agent",
            input_summary=f"Researching: {blackboard.topic}",
            visible_reasoning="Searching the web for ranking concepts and clip ideas.",
        )
        save_blackboard(blackboard)
        await self.delay()
        blackboard.topic_research = self._build_topic_research(blackboard)
        self._complete_trace(
            research_trace,
            output_summary=f"{self.pack.ranking_count} concepts discovered",
            visible_reasoning="Topic research complete — candidate slots ready.",
            tool_calls=[{"tool": "demo_tavily_research", "concepts": self.pack.ranking_count}],
        )
        blackboard.stage = "topic_researched"
        save_blackboard(blackboard)
        return blackboard

    async def discover_candidates(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        from app.services.candidate_review_service import CandidateReviewService

        discovery_trace = self._start_trace(
            blackboard,
            agent_id="candidate_discovery",
            agent_name="Candidate Discovery",
            input_summary=f"Topic: {blackboard.topic or self.pack.topic}",
            visible_reasoning="Preparing sequential review slots for web clip discovery.",
        )
        save_blackboard(blackboard)
        await self.delay()

        review_service = CandidateReviewService()
        blackboard.candidate_pool = []
        blackboard.selected_candidates = []
        blackboard.approved_candidates = []
        blackboard.rejected_candidates = []
        blackboard = review_service.initialize_queue(blackboard)

        self._complete_trace(
            discovery_trace,
            output_summary=f"Prepared {len(blackboard.candidate_review_queue)} concepts for sequential review",
            visible_reasoning="Concepts ready. Each slot will search, download, analyse, then wait for approval.",
        )
        blackboard.stage = "concepts_discovered"
        save_blackboard(blackboard)
        return blackboard

    async def prepare_slot(
        self,
        blackboard: ProjectBlackboard,
        slot: CandidateReviewSlot,
    ) -> ProjectBlackboard:
        rank_number = slot.slot_rank
        is_reject_variant = self._should_offer_reject_variant(slot)
        source_path = (
            self._resolve_reject_source_path(rank_number)
            if is_reject_variant
            else self.pack.candidate_files.get(rank_number)
        )
        if source_path is None:
            slot.status = "exhausted"
            slot.last_error = f"Demo clip missing for rank #{rank_number}"
            blackboard.selected_candidates = []
            save_blackboard(blackboard)
            return blackboard

        topic = blackboard.topic or self.pack.topic
        slot_concept = (
            self._reject_concept_for_rank(rank_number, slot.concept)
            if is_reject_variant
            else slot.concept
        )
        search_query = f"{slot_concept} {topic} shorts"
        url_suffix = "reject" if is_reject_variant else "approved"

        swarm_parent_id = "platform_search_swarm"
        swarm_trace = self._start_trace(
            blackboard,
            agent_id=swarm_parent_id,
            agent_name="Platform Search Swarm",
            input_summary=f"Searching platforms for slot #{rank_number}: {slot_concept}",
            visible_reasoning="Coordinating Tavily-powered YouTube Shorts search.",
            metadata={"swarm": True, "slot_rank": rank_number},
        )
        tavily_trace = self._start_swarm_child_trace(
            blackboard,
            parent_agent_id=swarm_parent_id,
            agent_id="youtube_shorts_search",
            agent_name="Tavily YouTube Search",
            input_summary=f"Tavily search for slot #{rank_number}: {slot_concept}",
            visible_reasoning=f"Running Tavily YouTube Shorts search for '{search_query}'.",
        )
        self._append_download_event(
            blackboard,
            agent_id="youtube_shorts_search",
            agent_name="Tavily YouTube Search",
            concept=slot_concept,
            stage="search_started",
            search_query=search_query,
            platform="youtube",
        )
        save_blackboard(blackboard)
        await self.delay(DEMO_CANDIDATE_STEP_DELAY_SEC)

        fake_source_url = f"{self.pack.youtube_url}#demo_rank_{rank_number}_{url_suffix}"
        self._append_download_event(
            blackboard,
            agent_id="youtube_shorts_search",
            agent_name="Tavily YouTube Search",
            concept=slot_concept,
            stage="url_selected",
            search_query=search_query,
            source_url=fake_source_url,
            platform="youtube",
        )
        self._complete_trace(
            tavily_trace,
            output_summary="Selected demo clip URL via Tavily",
            visible_reasoning=(
                "Tavily found a clip, but topic match is too weak for this ranking slot."
                if is_reject_variant
                else "Tavily found a Shorts clip matching reference constraints."
            ),
        )
        self._complete_trace(
            swarm_trace,
            output_summary="Platform search swarm complete",
            visible_reasoning="Tavily YouTube search finished for this slot.",
            tool_calls=[{"tool": "demo_tavily_youtube_search", "slot_rank": rank_number}],
        )
        save_blackboard(blackboard)
        await self.delay(DEMO_CANDIDATE_STEP_DELAY_SEC)

        candidate_id = new_id("cand")
        download_trace = self._start_trace(
            blackboard,
            agent_id=DEMO_AGENT_PLATFORM_VIDEO_DOWNLOAD,
            agent_name="Platform Video Download",
            input_summary=f"Downloading clip for rank #{rank_number}",
            visible_reasoning="Fetching clip into project workspace.",
        )
        self._append_download_event(
            blackboard,
            agent_id=DEMO_AGENT_PLATFORM_VIDEO_DOWNLOAD,
            agent_name="Platform Video Download",
            concept=slot_concept,
            stage="download_started",
            candidate_id=candidate_id,
            source_url=fake_source_url,
            platform="youtube",
        )
        save_blackboard(blackboard)
        await self.delay(DEMO_CANDIDATE_STEP_DELAY_SEC)

        file_suffix = "reject" if is_reject_variant else "approved"
        target_path = (
            self.project_candidates_dir(blackboard.project_id) / f"demo_rank_{rank_number}_{file_suffix}.mp4"
        )
        shutil.copy2(source_path, target_path)
        file_size = target_path.stat().st_size
        duration_sec = await get_video_duration(str(target_path))

        self._append_download_event(
            blackboard,
            agent_id=DEMO_AGENT_PLATFORM_VIDEO_DOWNLOAD,
            agent_name="Platform Video Download",
            concept=slot_concept,
            stage="download_success",
            candidate_id=candidate_id,
            source_url=fake_source_url,
            local_file_path=str(target_path),
            platform="youtube",
            file_size_bytes=file_size,
        )
        self._complete_trace(
            download_trace,
            output_summary=f"Downloaded {file_size // 1024}KB clip",
            visible_reasoning="Clip ready for Gemini analysis.",
        )
        save_blackboard(blackboard)
        await self.delay(DEMO_CANDIDATE_STEP_DELAY_SEC)

        base_score = 0.82 + (0.02 * (self.pack.ranking_count - rank_number))
        if is_reject_variant:
            topic_match_score = 0.32
            visual_quality_score = 0.62
            audio_quality_score = 0.55
            motion_energy_score = 0.58
            text_relevance_score = 0.28
            reference_style_fit_score = 0.52
            overall_score = 0.41
            reason = (
                "Visually acceptable, but the moment is not strong enough for this ranking topic. "
                "Low topic relevance and weak fit for this slot's concept."
            )
            highlight_reason = "Off-topic for this rank — reject and find a clip that better matches the theme."
        else:
            topic_match_score = min(base_score + 0.05, 0.98)
            visual_quality_score = min(base_score + 0.03, 0.97)
            audio_quality_score = base_score
            motion_energy_score = min(base_score + 0.04, 0.96)
            text_relevance_score = base_score
            reference_style_fit_score = min(base_score + 0.06, 0.99)
            overall_score = min(base_score + 0.04, 0.97)
            reason = (
                f"Strong Shorts clip for rank #{rank_number} — matches reference pacing and 9:16 format."
            )
            highlight_reason = f"Best moment for rank #{rank_number} in the {topic} ranking."

        candidate = CandidateVideo(
            candidate_id=candidate_id,
            project_id=blackboard.project_id,
            title=slot_concept,
            source_type="sample_asset",
            source_url=fake_source_url,
            local_file_path=str(target_path),
            concept=slot_concept,
            duration_sec=duration_sec,
            topic_match_score=topic_match_score,
            visual_quality_score=visual_quality_score,
            audio_quality_score=audio_quality_score,
            motion_energy_score=motion_energy_score,
            text_relevance_score=text_relevance_score,
            reference_style_fit_score=reference_style_fit_score,
            source_safety_score=0.95,
            overall_score=overall_score,
            reason=reason,
            status="selected",
            recommended_rank=rank_number,
            highlight_reason=highlight_reason,
            video_moment_title=slot_concept,
        )

        if blackboard.reference_blueprint:
            candidate = apply_reference_segment_to_candidate(candidate, blackboard.reference_blueprint)
            candidate.duration_sec = duration_sec or candidate.duration_sec

        candidate = enrich_candidate_story_fields(candidate)
        thumb_path = str(target_path.with_suffix(".thumb.jpg"))
        try:
            await generate_thumbnail(
                str(target_path),
                thumb_path,
                at_sec=candidate.clip_start_sec or 1.0,
            )
            candidate.thumbnail_path = thumb_path
        except Exception:
            pass

        analysis_agents = [
            (DEMO_AGENT_CANDIDATE_VISUAL_ANALYSIS, "Visual & Topic Analysis", "Scoring visual quality and topic fit."),
            (DEMO_AGENT_CANDIDATE_SEGMENT, "Segment Selection", "Selecting the best highlight window inside the clip."),
            (DEMO_AGENT_CANDIDATE_PREVIEW, "Preview Generator", "Generating preview thumbnail."),
        ]
        for agent_id, agent_name, reasoning in analysis_agents:
            analysis_trace = self._start_trace(
                blackboard,
                agent_id=agent_id,
                agent_name=agent_name,
                input_summary=f"Analysing rank #{rank_number} clip",
                visible_reasoning=reasoning,
            )
            save_blackboard(blackboard)
            await self.delay(DEMO_CANDIDATE_STEP_DELAY_SEC * 0.6)
            self._complete_trace(
                analysis_trace,
                output_summary=f"Rank #{rank_number} analysis complete",
                visible_reasoning=reasoning,
                tool_calls=[{"tool": "demo_candidate_analysis", "rank": rank_number}],
            )
            save_blackboard(blackboard)

        save_candidate_video_analysis(
            blackboard,
            candidate,
            analysis_source=DEMO_ANALYSIS_SOURCE,
        )

        slot.current_candidate = candidate
        slot.status = SLOT_STATUS_AWAITING_APPROVAL
        slot.last_error = None
        candidate.status = "selected"
        blackboard.selected_candidates = [candidate]
        if candidate not in blackboard.candidate_pool:
            blackboard.candidate_pool.append(candidate)
        blackboard.stage = "awaiting_candidate_approval"
        save_blackboard(blackboard)
        return blackboard

    def _simulate_moe_state(self, blackboard: ProjectBlackboard) -> None:
        round_id = new_id("round")
        blackboard.moe_routing = MoERoutingWeights(
            round_id=round_id,
            story=0.3,
            cut=0.25,
            caption=0.25,
            motion=0.2,
            reasoning="Demo MoE routing weighted toward story and captions for ranking Shorts.",
        )
        candidates = blackboard.approved_candidates or blackboard.selected_candidates
        clip_adjustments = [
            {
                "rank": candidate.recommended_rank or index + 1,
                "clip_start_sec": candidate.clip_start_sec or 0.0,
                "clip_end_sec": candidate.clip_end_sec or min(candidate.duration_sec or 4.0, 5.0),
            }
            for index, candidate in enumerate(sorted(candidates, key=lambda item: item.recommended_rank or 99))
        ]
        caption_updates = [
            {
                "rank": candidate.recommended_rank or index + 1,
                "label_text": f"#{candidate.recommended_rank or index + 1}",
                "caption_text": candidate.concept[:80],
                "voiceover_text": f"Number {candidate.recommended_rank or index + 1}: {candidate.concept}",
            }
            for index, candidate in enumerate(sorted(candidates, key=lambda item: item.recommended_rank or 99))
        ]
        blackboard.moe_fusion = MoEFusionResult(
            fusion_id=new_id("fusion"),
            round_id=round_id,
            hook_text=f"Top {len(candidates)} {blackboard.topic or self.pack.topic}",
            outro_text="Which one wins for you?",
            clip_adjustments=clip_adjustments,
            caption_updates=caption_updates,
            motion_updates=[
                {"rank": 1, "zoom": True, "pan": False, "scale": 1.05},
            ],
            transition_updates=[{"rank": rank, "type": "hard_cut"} for rank in range(1, len(candidates) + 1)],
            routing_weights=blackboard.moe_routing,
            expert_contributions={"story": 0.3, "cut": 0.25, "caption": 0.25, "motion": 0.2},
            consensus_notes=["Demo fusion aligned clips to reference countdown structure."],
        )
        blackboard.expert_proposals = [
            ExpertProposal(
                proposal_id=new_id("prop"),
                agent_id="story_expert",
                agent_name="Story Expert",
                domain="story",
                round_id=round_id,
                confidence=0.88,
                hook_text=blackboard.moe_fusion.hook_text,
                outro_text=blackboard.moe_fusion.outro_text,
                reasoning="Countdown narrative with stronger rank #1 emphasis.",
            )
        ]
        blackboard.agent_messages = [
            AgentMessage(
                message_id=new_id("msg"),
                project_id=blackboard.project_id,
                run_id=blackboard.run_id,
                round_id=round_id,
                from_agent_id="story_expert",
                from_agent_name="Story Expert",
                message_type="proposal",
                domain="story",
                payload={"hook": blackboard.moe_fusion.hook_text},
                created_at=utc_now(),
            )
        ]

    async def create_edit_plan(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if blackboard.edit_plan is not None:
            self._reset_edit_plan_swarm_state(blackboard)

        moe_trace = self._start_trace(
            blackboard,
            agent_id="moe_edit_swarm",
            agent_name="MoE Edit Swarm",
            input_summary="Running Story, Cut, Caption, Motion experts",
            visible_reasoning="Experts proposing parallel edit adjustments.",
        )
        save_blackboard(blackboard)
        await self.delay()
        self._simulate_moe_state(blackboard)
        self._complete_trace(
            moe_trace,
            output_summary="Expert proposals fused into edit plan",
            visible_reasoning="MoE swarm reached consensus on hook, captions, and motion.",
        )
        save_blackboard(blackboard)
        await self.delay()

        fusion_trace = self._start_trace(
            blackboard,
            agent_id="fusion_agent",
            agent_name="Fusion Agent",
            input_summary="Merging weighted expert proposals",
            visible_reasoning="Applying fused clip, caption, and motion adjustments.",
        )
        save_blackboard(blackboard)
        await self.delay()
        self._complete_trace(
            fusion_trace,
            output_summary="Fusion complete",
            visible_reasoning="Edit plan sections aligned to reference blueprint.",
        )
        save_blackboard(blackboard)
        await self.delay()

        build_state = await workflow_nodes.build_edit_plan_node({"blackboard": blackboard})
        blackboard = build_state["blackboard"]
        self._append_rejection_learning_to_edit_plan(blackboard)
        self._apply_studio_feedback_to_edit_plan(blackboard)
        save_blackboard(blackboard)

        audio_trace = self._start_trace(
            blackboard,
            agent_id="slng_audio",
            agent_name="SLNG Audio Agent",
            input_summary="Generating voiceover plan",
            visible_reasoning="Matching reference audio energy without external API in demo mode.",
        )
        save_blackboard(blackboard)
        await self.delay()
        self._complete_trace(
            audio_trace,
            output_summary="Audio plan applied from reference blueprint",
            visible_reasoning="Voiceover optional — reference music style preserved.",
        )
        save_blackboard(blackboard)
        await self.delay()

        critic_trace = self._start_trace(
            blackboard,
            agent_id="critic_agent",
            agent_name="Critic Agent",
            input_summary="Validating edit plan goals",
            visible_reasoning="Checking story coherence and ranking structure.",
        )
        save_blackboard(blackboard)
        await self.delay()
        blackboard.harness_goals_met = True
        self._complete_trace(
            critic_trace,
            output_summary="Edit plan goals met",
            visible_reasoning="Story coherence and ranking structure validated.",
        )

        if blackboard.edit_plan is not None:
            blackboard.edit_plan.needs_human_approval = True
        blackboard.waiting_for_human = True
        blackboard.human_gate_type = "edit_plan_approval"
        blackboard.stage = "edit_plan_ready"
        save_blackboard(blackboard)
        return blackboard

    async def render(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        version = blackboard.current_version
        output_dir = self.settings.output_dir / blackboard.project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{blackboard.project_id}_v{version}.mp4"

        await self._simulate_render_pipeline(blackboard, output_path=output_path)

        blackboard.output_video_path = str(output_path)
        blackboard.waiting_for_human = False
        blackboard.human_gate_type = None
        blackboard.stage = "rendered"
        save_blackboard(blackboard)
        return blackboard

    async def compare(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        comparison_trace = self._start_trace(
            blackboard,
            agent_id="comparison_agent",
            agent_name="Comparison Agent",
            input_summary="Comparing reference vs generated output",
            visible_reasoning="Scoring structure, pacing, captions, and topic relevance.",
        )
        save_blackboard(blackboard)
        await self.delay()

        blueprint = blackboard.reference_blueprint
        edit_plan = blackboard.edit_plan
        ranking_match = 0.9
        if blueprint and edit_plan and abs(blueprint.ranking_count - len(edit_plan.sections)) > 1:
            ranking_match = 0.75

        learned: list[str] = []
        for update in blackboard.memory_updates:
            for item in update.get("long_term_updates", []):
                content = item.get("content", "")
                if content:
                    learned.append(content)

        improvements = [
            "Applied stronger emphasis on rank #1",
            "Matched reference Shorts pacing and vertical format",
        ]
        for feedback in blackboard.feedback_events:
            if feedback.feedback_text:
                improvements.append(f"Applied feedback: {feedback.feedback_text}")

        blackboard.comparison_report = ComparisonReport(
            project_id=blackboard.project_id,
            reference_match_score=0.88,
            user_preference_match_score=0.85,
            pacing_match_score=0.86,
            caption_style_match_score=0.84,
            audio_style_match_score=0.8,
            ranking_structure_match_score=ranking_match,
            topic_relevance_score=0.91,
            issues=[],
            improvements_after_feedback=improvements,
            learned_preferences=learned,
        )
        self._complete_trace(
            comparison_trace,
            output_summary="Reference match score: 0.88",
            visible_reasoning="Generated ranking closely follows reference editing DNA.",
        )
        blackboard.stage = "compared"
        save_blackboard(blackboard)
        return blackboard

    async def apply_feedback(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        recent_feedback = blackboard.feedback_events[-5:]
        short_term: list[dict[str, str]] = []
        episodic: list[dict[str, str]] = []
        long_term: list[dict[str, str]] = []

        for feedback in recent_feedback:
            sentiment = classify_feedback_sentiment(feedback.feedback_text, feedback.feedback_type)
            scoped_short, scoped_episodic, scoped_long = build_memory_scope_updates(feedback, sentiment)
            short_term.extend(scoped_short)
            episodic.extend(scoped_episodic)
            long_term.extend(scoped_long)

        feedback_trace = self._start_trace(
            blackboard,
            agent_id="mubit_memory",
            agent_name="Mubit Memory Agent",
            input_summary="Saving feedback to memory",
            visible_reasoning="Updating short-term, episodic, and long-term preferences.",
        )
        save_blackboard(blackboard)
        await self.delay()

        latest_sentiment = (
            classify_feedback_sentiment(
                recent_feedback[-1].feedback_text,
                recent_feedback[-1].feedback_type,
            )
            if recent_feedback
            else "neutral"
        )
        summary = (
            feedback_memory_summary(
                short_term_count=len(short_term),
                episodic_count=len(episodic),
                long_term_count=len(long_term),
                sentiment=latest_sentiment,
                mubit_synced=True,
            )
            if recent_feedback
            else "Feedback stored"
        )
        self._append_memory_update(
            blackboard,
            short_term=short_term,
            episodic=episodic,
            long_term=long_term,
            summary=summary,
            confidence=0.85 if short_term else 0.5,
        )
        self._complete_trace(
            feedback_trace,
            output_summary=summary,
            visible_reasoning="Creative director feedback captured for future rankings.",
        )
        blackboard.stage = "feedback_applied"
        save_blackboard(blackboard)
        return blackboard

    async def regenerate(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        prepare_state = await workflow_nodes.prepare_regenerate_node({"blackboard": blackboard})
        blackboard = prepare_state["blackboard"]
        blackboard = await self.create_edit_plan(blackboard)
        blackboard = await self.render(blackboard)
        return blackboard

    async def clear_human_gate(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        blackboard.waiting_for_human = False
        blackboard.human_gate_type = None
        save_blackboard(blackboard)
        return blackboard
