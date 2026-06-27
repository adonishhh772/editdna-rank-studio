from pathlib import Path

from app.agents.platform_video_download_agent import PlatformVideoDownloadAgent
from app.blackboard import ProjectBlackboard
from app.constants.candidate_review import (
    MAX_DOWNLOAD_TRIES_PER_SLOT,
    MAX_PREPARE_SLOTS_PER_REQUEST,
    PLATFORM_SEARCH_HIT_POOL_KEY,
    SLOT_STATUS_APPROVED,
    SLOT_STATUS_AWAITING_APPROVAL,
    SLOT_STATUS_EXHAUSTED,
    SLOT_STATUS_PENDING,
    SLOT_STATUS_PREPARING,
)
from app.constants.video_constraints import PREFERENCE_DECISION_APPROVE, PREFERENCE_DECISION_REJECT
from app.agents.platform_search_swarm_agent import PlatformSearchSwarmAgent
from app.constants.video_sources import DEFAULT_RANKING_COUNT, detect_video_orientation_from_dimensions
from app.db import new_id, save_blackboard, utc_now
from app.agents.candidate_analysis_swarm_agent import analyze_candidate_with_swarm
from app.schemas import AgentTrace, CandidateReviewSlot, CandidateReviewStatusResponse, CandidateVideo, MemoryUpdate
from app.services.candidate_preference_service import (
    apply_candidate_decision_to_preferences,
    build_candidate_feedback_event,
    persist_candidate_preference_memory,
    preference_blocked_orientations,
    preference_max_duration_sec,
)
from app.services.video_constraint_service import (
    ReferenceVideoConstraints,
    VideoFitEvaluation,
    build_rejection_message,
    evaluate_video_fit,
)
from app.services.concept_sanitizer import (
    build_topic_shorts_search_query,
    normalize_research_concepts,
)
from app.services.preference_learning_service import should_use_lightweight_selection
from app.constants.video_analysis import ANALYSIS_SOURCE_GEMINI, ANALYSIS_SOURCE_LIGHTWEIGHT
from app.services.segment_selection_service import apply_reference_segment_to_candidate
from app.services.story_coherence_service import enrich_candidate_story_fields
from app.services.video_analysis_store import save_candidate_video_analysis
from app.services.video_utils import generate_thumbnail, get_video_dimensions, get_video_duration
from app.services.web_video_fetch import PlatformSearchHit, WebVideoFetchService


class CandidateReviewService:
    def ranking_count(self, blackboard: ProjectBlackboard) -> int:
        if blackboard.reference_blueprint:
            return blackboard.reference_blueprint.ranking_count
        if blackboard.topic_research:
            return blackboard.topic_research.ranking_count
        return DEFAULT_RANKING_COUNT

    def build_status(self, blackboard: ProjectBlackboard) -> CandidateReviewStatusResponse:
        queue = blackboard.candidate_review_queue
        approved_count = sum(1 for slot in queue if slot.status == SLOT_STATUS_APPROVED)
        pending_count = sum(
            1
            for slot in queue
            if slot.status in {SLOT_STATUS_PENDING, SLOT_STATUS_PREPARING, SLOT_STATUS_AWAITING_APPROVAL}
        )
        exhausted_count = sum(1 for slot in queue if slot.status == SLOT_STATUS_EXHAUSTED)
        active_slot = self._find_active_review_slot(blackboard)

        current_candidate = None
        current_status = None
        current_slot_rank = None
        message = ""

        if active_slot:
            current_slot_rank = active_slot.slot_rank
            current_status = active_slot.status
            current_candidate = active_slot.current_candidate
            if active_slot.last_error:
                message = active_slot.last_error
            elif active_slot.status == SLOT_STATUS_AWAITING_APPROVAL:
                message = f"Review slot #{active_slot.slot_rank}"
            elif active_slot.status == SLOT_STATUS_EXHAUSTED:
                message = f"No suitable video found for slot #{active_slot.slot_rank}"
        elif queue and approved_count == len(queue):
            message = "All slots approved"
        elif not queue:
            message = "Review queue not initialized"

        return CandidateReviewStatusResponse(
            review_active=blackboard.review_active,
            total_slots=len(queue),
            approved_count=approved_count,
            pending_count=pending_count,
            exhausted_count=exhausted_count,
            current_slot_rank=current_slot_rank,
            current_status=current_status,
            current_candidate=current_candidate,
            message=message,
        )

    def initialize_queue(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.topic_research:
            raise RuntimeError("Topic research is required before candidate review")

        slot_count = self.ranking_count(blackboard)
        raw_concepts = blackboard.topic_research.candidate_concepts[:slot_count]
        concepts = normalize_research_concepts(
            raw_concepts,
            topic=blackboard.topic or blackboard.topic_research.topic,
            ranking_count=slot_count,
        )
        if not concepts:
            raise RuntimeError("No candidate concepts available from research")

        blackboard.candidate_review_queue = [
            CandidateReviewSlot(slot_rank=index, concept=concept)
            for index, concept in enumerate(concepts, start=1)
        ]
        blackboard.review_active = True
        blackboard.selected_candidates = []
        blackboard.stage = "candidate_review_initialized"
        save_blackboard(blackboard)
        return blackboard

    async def start_review(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.candidate_review_queue:
            blackboard = self.initialize_queue(blackboard)

        awaiting_slot = self._find_awaiting_slot(blackboard)
        if awaiting_slot and awaiting_slot.current_candidate:
            blackboard.selected_candidates = [awaiting_slot.current_candidate]
            blackboard.stage = "awaiting_candidate_approval"
            save_blackboard(blackboard)
            return blackboard

        preparing_slot = next(
            (slot for slot in blackboard.candidate_review_queue if slot.status == SLOT_STATUS_PREPARING),
            None,
        )
        if preparing_slot:
            return await self._prepare_slot(blackboard, preparing_slot)

        return await self.prepare_next_slot(blackboard)

    async def prepare_next_slot(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        prepare_attempts = 0
        while prepare_attempts < MAX_PREPARE_SLOTS_PER_REQUEST:
            if self._find_awaiting_slot(blackboard):
                break

            slot = self._find_next_pending_slot(blackboard)
            if slot is None:
                if self._all_slots_resolved(blackboard):
                    blackboard.stage = (
                        "candidates_approved"
                        if blackboard.approved_candidates
                        else "candidate_review_complete"
                    )
                    blackboard.selected_candidates = []
                break

            await self._prepare_slot(blackboard, slot)
            prepare_attempts += 1

            if self._find_awaiting_slot(blackboard):
                break

        save_blackboard(blackboard)
        return blackboard

    async def skip_current_slot(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        slot = self._find_awaiting_slot(blackboard) or self._find_next_pending_slot(blackboard)
        if slot is None:
            save_blackboard(blackboard)
            return blackboard

        slot.current_candidate = None
        slot.status = SLOT_STATUS_EXHAUSTED
        slot.last_error = "Skipped — continuing without a clip for this slot"
        blackboard.selected_candidates = []
        save_blackboard(blackboard)
        return await self.prepare_next_slot(blackboard)

    async def approve_candidate(
        self,
        blackboard: ProjectBlackboard,
        candidate_id: str,
    ) -> ProjectBlackboard:
        already_approved = next(
            (item for item in blackboard.approved_candidates if item.candidate_id == candidate_id),
            None,
        )
        if already_approved is not None:
            blackboard.selected_candidates = []
            save_blackboard(blackboard)
            return blackboard

        slot = self._find_slot_by_candidate_id(blackboard, candidate_id)
        if slot is None or slot.current_candidate is None:
            raise RuntimeError("Candidate is not awaiting approval")

        await self._record_human_decision(
            blackboard,
            slot.current_candidate,
            PREFERENCE_DECISION_APPROVE,
        )

        approved = slot.current_candidate.model_copy(deep=True)
        approved.status = "approved"
        approved.recommended_rank = slot.slot_rank
        slot.approved_candidate = approved
        slot.current_candidate = None
        slot.status = SLOT_STATUS_APPROVED
        slot.last_error = None

        if approved not in blackboard.approved_candidates:
            blackboard.approved_candidates.append(approved)

        blackboard.candidate_pool = [
            item for item in blackboard.candidate_pool if item.candidate_id != candidate_id
        ] + [approved]
        blackboard.selected_candidates = []
        save_blackboard(blackboard)
        return blackboard

    async def reject_candidate(
        self,
        blackboard: ProjectBlackboard,
        candidate_id: str,
    ) -> ProjectBlackboard:
        slot = self._find_slot_by_candidate_id(blackboard, candidate_id)
        if slot is None or slot.current_candidate is None:
            raise RuntimeError("Candidate is not awaiting approval")

        rejected = slot.current_candidate.model_copy(deep=True)
        rejected.status = "rejected"
        blackboard.rejected_candidates.append(rejected)

        await self._record_human_decision(
            blackboard,
            rejected,
            PREFERENCE_DECISION_REJECT,
        )

        if rejected.source_url and rejected.source_url not in slot.rejected_urls:
            slot.rejected_urls.append(rejected.source_url)

        slot.current_candidate = None
        slot.status = SLOT_STATUS_PENDING
        slot.last_error = None

        blackboard.selected_candidates = []
        save_blackboard(blackboard)
        return blackboard

    async def _prepare_slot(self, blackboard: ProjectBlackboard, slot: CandidateReviewSlot) -> ProjectBlackboard:
        slot.status = SLOT_STATUS_PREPARING
        slot.last_error = None
        blackboard.selected_candidates = []
        save_blackboard(blackboard)

        try:
            return await self._prepare_slot_inner(blackboard, slot)
        except Exception as exc:
            if slot.status == SLOT_STATUS_PREPARING:
                slot.status = SLOT_STATUS_PENDING
                slot.last_error = str(exc)
            blackboard.selected_candidates = []
            save_blackboard(blackboard)
            raise

    async def _prepare_slot_inner(
        self,
        blackboard: ProjectBlackboard,
        slot: CandidateReviewSlot,
    ) -> ProjectBlackboard:
        from app.services.demo_pack_loader import is_demo_mode_active
        from app.services.demo_replay_service import DemoReplayService

        if is_demo_mode_active():
            demo = DemoReplayService.active()
            return await demo.prepare_slot(blackboard, slot)

        topic = blackboard.topic or ""
        youtube_search_mode = (
            blackboard.topic_research.youtube_search_mode if blackboard.topic_research else None
        )
        constraints = WebVideoFetchService.build_constraints_from_blueprint(blackboard.reference_blueprint)
        search_constraints = (
            constraints.for_platform_search(youtube_search_mode) if constraints else None
        )
        acceptance_constraints = (
            constraints.for_source_acceptance(youtube_search_mode) if constraints else None
        )

        hits = await self._search_platform_hits(
            blackboard,
            topic=topic,
            slot=slot,
            youtube_search_mode=youtube_search_mode,
        )

        if not hits:
            constraint_hint = ""
            if search_constraints:
                constraint_hint = (
                    f" near ~{search_constraints.target_candidate_duration_sec:.0f}s "
                    f"({search_constraints.min_source_duration_sec:.0f}–"
                    f"{search_constraints.max_source_duration_sec:.0f}s), "
                    f"{search_constraints.aspect_ratio}"
                )
            slot.status = SLOT_STATUS_EXHAUSTED
            slot.last_error = (
                f"No more Shorts available for topic '{topic or slot.concept}'{constraint_hint}"
            )
            blackboard.selected_candidates = []
            save_blackboard(blackboard)
            return blackboard

        download_tries = 0
        for hit in hits:
            if download_tries >= MAX_DOWNLOAD_TRIES_PER_SLOT:
                break
            download_tries += 1
            candidate = CandidateVideo(
                candidate_id=new_id("cand"),
                project_id=blackboard.project_id,
                title=hit.title,
                source_type="public_url_reference",
                source_url=hit.url,
                concept=slot.concept,
                duration_sec=hit.duration_sec,
                topic_match_score=0.55,
                visual_quality_score=0.0,
                audio_quality_score=0.0,
                motion_energy_score=0.0,
                text_relevance_score=0.65,
                reference_style_fit_score=hit.fit_score,
                source_safety_score=0.85,
                overall_score=hit.fit_score,
                reason=_build_candidate_reason(hit),
                status="selected",
                recommended_rank=slot.slot_rank,
            )

            download_agent = PlatformVideoDownloadAgent()
            download_result = await download_agent.download_single_candidate(blackboard, candidate)
            if download_result and download_result.success and download_result.local_file_path:
                candidate.local_file_path = download_result.local_file_path

            if not download_result or not download_result.success or not candidate.local_file_path:
                if candidate.source_url and candidate.source_url not in slot.rejected_urls:
                    slot.rejected_urls.append(candidate.source_url)
                slot.last_error = (
                    download_result.error if download_result and download_result.error else "Download failed"
                )
                continue

            validation = await self._validate_local_candidate(
                blackboard,
                candidate,
                hit,
                acceptance_constraints,
            )
            if not validation.acceptable:
                if candidate.source_url and candidate.source_url not in slot.rejected_urls:
                    slot.rejected_urls.append(candidate.source_url)
                slot.last_error = build_rejection_message(validation, constraints) if constraints else "Video rejected"
                continue

            use_lightweight, learning_reasons = should_use_lightweight_selection(
                blackboard.memory_context,
                duration_sec=candidate.duration_sec,
                orientation=hit.orientation,
                aspect_ratio_hint=hit.aspect_ratio_hint,
                target_duration_sec=(
                    constraints.target_candidate_duration_sec if constraints else None
                ),
            )

            try:
                if use_lightweight:
                    candidate = await self._apply_lightweight_selection(
                        blackboard,
                        candidate,
                        learning_reasons,
                    )
                else:
                    candidate = await self._analyze_candidate(blackboard, candidate)
            except Exception:
                if candidate.source_url and candidate.source_url not in slot.rejected_urls:
                    slot.rejected_urls.append(candidate.source_url)
                continue

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

        slot.search_attempts += 1
        slot.status = SLOT_STATUS_EXHAUSTED
        slot.last_error = slot.last_error or (
            f"Could not download a topic clip for '{topic or slot.concept}' — skip or continue"
        )
        blackboard.selected_candidates = []
        save_blackboard(blackboard)
        return blackboard

    def _collect_blocked_urls(
        self,
        blackboard: ProjectBlackboard,
        slot: CandidateReviewSlot | None = None,
    ) -> set[str]:
        blocked: set[str] = set()
        if slot is not None:
            blocked.update(slot.rejected_urls)
        for review_slot in blackboard.candidate_review_queue:
            blocked.update(review_slot.rejected_urls)
        for candidate in blackboard.approved_candidates:
            if candidate.source_url:
                blocked.add(candidate.source_url)
        for candidate in blackboard.rejected_candidates:
            if candidate.source_url:
                blocked.add(candidate.source_url)
        awaiting_slot = self._find_awaiting_slot(blackboard)
        if awaiting_slot and awaiting_slot.current_candidate and awaiting_slot.current_candidate.source_url:
            blocked.add(awaiting_slot.current_candidate.source_url)
        return blocked

    async def _ensure_platform_hit_pool(
        self,
        blackboard: ProjectBlackboard,
        *,
        topic: str,
        youtube_search_mode: str | None,
    ) -> list[dict[str, object]]:
        cached_pool = blackboard.memory_context.get(PLATFORM_SEARCH_HIT_POOL_KEY)
        if isinstance(cached_pool, list) and cached_pool:
            return cached_pool

        search_concept = build_topic_shorts_search_query(topic)
        blackboard.memory_context["_platform_search_request"] = {
            "concept": search_concept,
            "topic": topic,
            "exclude_urls": [],
            "youtube_search_mode": youtube_search_mode,
        }
        save_blackboard(blackboard)

        swarm_agent = PlatformSearchSwarmAgent()
        blackboard = await swarm_agent.execute(blackboard, swarm=True)
        merged_raw = blackboard.memory_context.pop("_platform_search_merged_hits", [])
        blackboard.memory_context.pop("_platform_search_request", None)
        blackboard.memory_context[PLATFORM_SEARCH_HIT_POOL_KEY] = merged_raw
        save_blackboard(blackboard)
        return merged_raw

    async def _search_platform_hits(
        self,
        blackboard: ProjectBlackboard,
        *,
        topic: str,
        slot: CandidateReviewSlot,
        youtube_search_mode: str | None,
    ) -> list[PlatformSearchHit]:
        fetch_service = WebVideoFetchService()
        pool_raw = await self._ensure_platform_hit_pool(
            blackboard,
            topic=topic,
            youtube_search_mode=youtube_search_mode,
        )
        blocked_urls = self._collect_blocked_urls(blackboard, slot)
        available_hits = [
            hit
            for hit in pool_raw
            if str(hit.get("url") or "") and str(hit.get("url")) not in blocked_urls
        ]
        return fetch_service.hits_from_dicts(available_hits)

    async def _validate_local_candidate(
        self,
        blackboard: ProjectBlackboard,
        candidate: CandidateVideo,
        hit: PlatformSearchHit | None = None,
        constraints_override: ReferenceVideoConstraints | None = None,
    ) -> VideoFitEvaluation:
        constraints = constraints_override or WebVideoFetchService.build_constraints_from_blueprint(
            blackboard.reference_blueprint
        )
        if constraints is None:
            return VideoFitEvaluation(acceptable=True, fit_score=1.0)

        duration_sec = candidate.duration_sec
        width = hit.width if hit else None
        height = hit.height if hit else None
        aspect_ratio_hint = hit.aspect_ratio_hint if hit and hit.aspect_ratio_hint else "unknown"
        orientation = hit.orientation if hit and hit.orientation else "unknown"

        if candidate.local_file_path and Path(candidate.local_file_path).exists():
            duration_sec = await get_video_duration(candidate.local_file_path) or duration_sec
            probed_width, probed_height = await get_video_dimensions(candidate.local_file_path)
            width = probed_width or width
            height = probed_height or height
            orientation = detect_video_orientation_from_dimensions(width, height)
            candidate.duration_sec = duration_sec

        return evaluate_video_fit(
            duration_sec=duration_sec,
            width=width,
            height=height,
            orientation=orientation or "unknown",
            aspect_ratio_hint=aspect_ratio_hint,
            constraints=constraints,
            preference_max_duration_sec=preference_max_duration_sec(blackboard.memory_context),
            blocked_orientations=preference_blocked_orientations(blackboard.memory_context),
        )

    async def _record_human_decision(
        self,
        blackboard: ProjectBlackboard,
        candidate: CandidateVideo,
        decision: str,
    ) -> None:
        constraints = WebVideoFetchService.build_constraints_from_blueprint(blackboard.reference_blueprint)
        evaluation = await self._validate_local_candidate(blackboard, candidate)
        feedback = build_candidate_feedback_event(
            blackboard_user_id=blackboard.user_id,
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            candidate=candidate,
            decision=decision,
            evaluation=evaluation,
            constraints=constraints,
        )
        blackboard.feedback_events.append(feedback)
        blackboard.memory_context = apply_candidate_decision_to_preferences(
            blackboard.memory_context,
            candidate=candidate,
            decision=decision,
            evaluation=evaluation,
            constraints=constraints,
        )
        blackboard.memory_updates.append(
            MemoryUpdate(
                memory_update_id=new_id("mem"),
                project_id=blackboard.project_id,
                run_id=blackboard.run_id,
                user_id=blackboard.user_id,
                short_term_updates=[{"content": feedback.feedback_text or decision, "type": decision}],
                episodic_updates=[{"content": feedback.feedback_text or decision}],
                long_term_updates=(
                    [{"content": feedback.feedback_text or decision}] if decision == PREFERENCE_DECISION_REJECT else []
                ),
                confidence=0.9,
                summary=feedback.feedback_text or decision,
            ).model_dump()
        )
        await persist_candidate_preference_memory(
            user_id=blackboard.user_id,
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            agent_id="candidate_review",
            feedback=feedback,
        )
        save_blackboard(blackboard)

    async def _apply_lightweight_selection(
        self,
        blackboard: ProjectBlackboard,
        candidate: CandidateVideo,
        learning_reasons: list[str],
    ) -> CandidateVideo:
        if not blackboard.reference_blueprint:
            raise RuntimeError("Reference blueprint is required")
        if not candidate.local_file_path or not Path(candidate.local_file_path).exists():
            raise RuntimeError("Downloaded video file is missing")

        selected = candidate.model_copy(deep=True)
        selected = apply_reference_segment_to_candidate(selected, blackboard.reference_blueprint)
        selected.duration_sec = await get_video_duration(candidate.local_file_path)
        selected = enrich_candidate_story_fields(selected)
        learning_note = "; ".join(learning_reasons) if learning_reasons else "Matches learned preferences"
        selected.reason = (
            f"Auto-selected from learned preferences — {learning_note}. "
            "Skipping deep analysis; stitch-ready segment applied."
        )
        selected.status = "selected"

        thumb_at_sec = selected.clip_start_sec or 1.0
        thumb_path = str(Path(candidate.local_file_path).with_suffix(".thumb.jpg"))
        try:
            await generate_thumbnail(candidate.local_file_path, thumb_path, at_sec=thumb_at_sec)
            selected.thumbnail_path = thumb_path
        except Exception:
            pass

        trace = AgentTrace(
            trace_id=new_id("trace"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            agent_id="preference_auto_select",
            agent_name="Preference Auto-Select",
            status="complete",
            started_at=utc_now(),
            completed_at=utc_now(),
            input_summary=f"Lightweight selection for {candidate.concept}",
            output_summary=learning_note,
            visible_reasoning="Learned preferences matched — skipping Gemini analysis.",
        )
        blackboard.traces.append(trace)
        save_candidate_video_analysis(
            blackboard,
            selected,
            analysis_source=ANALYSIS_SOURCE_LIGHTWEIGHT,
        )
        save_blackboard(blackboard)
        return selected

    async def _analyze_candidate(
        self,
        blackboard: ProjectBlackboard,
        candidate: CandidateVideo,
    ) -> CandidateVideo:
        if not blackboard.reference_blueprint:
            raise RuntimeError("Reference blueprint is required")
        if not candidate.local_file_path or not Path(candidate.local_file_path).exists():
            raise RuntimeError("Downloaded video file is missing")

        blackboard, analyzed = await analyze_candidate_with_swarm(blackboard, candidate)
        analyzed = enrich_candidate_story_fields(analyzed)
        save_candidate_video_analysis(
            blackboard,
            analyzed,
            analysis_source=ANALYSIS_SOURCE_GEMINI,
        )
        save_blackboard(blackboard)
        return analyzed

    def _find_active_review_slot(self, blackboard: ProjectBlackboard) -> CandidateReviewSlot | None:
        awaiting_slot = self._find_awaiting_slot(blackboard)
        if awaiting_slot is not None:
            return awaiting_slot

        for slot in blackboard.candidate_review_queue:
            if slot.status == SLOT_STATUS_PREPARING:
                return slot

        return self._find_next_pending_slot(blackboard)

    def _find_next_pending_slot(self, blackboard: ProjectBlackboard) -> CandidateReviewSlot | None:
        for slot in blackboard.candidate_review_queue:
            if slot.status == SLOT_STATUS_PENDING:
                return slot
        return None

    def _find_awaiting_slot(self, blackboard: ProjectBlackboard) -> CandidateReviewSlot | None:
        for slot in blackboard.candidate_review_queue:
            if slot.status == SLOT_STATUS_AWAITING_APPROVAL:
                return slot
        return None

    def _find_slot_by_candidate_id(
        self,
        blackboard: ProjectBlackboard,
        candidate_id: str,
    ) -> CandidateReviewSlot | None:
        for slot in blackboard.candidate_review_queue:
            if slot.current_candidate and slot.current_candidate.candidate_id == candidate_id:
                return slot
        return None

    def _all_slots_resolved(self, blackboard: ProjectBlackboard) -> bool:
        if not blackboard.candidate_review_queue:
            return False
        resolved_statuses = {SLOT_STATUS_APPROVED, SLOT_STATUS_EXHAUSTED}
        return all(slot.status in resolved_statuses for slot in blackboard.candidate_review_queue)


def _build_candidate_reason(hit: PlatformSearchHit) -> str:
    base = "Matched reference duration and aspect constraints"
    if not hit.learning_reasons:
        return base
    learning = "; ".join(hit.learning_reasons)
    return f"{base}. Learning: {learning}"
