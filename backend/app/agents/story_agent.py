from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.constants.harness import MAX_HARNESS_REVISIONS
from app.constants.moe import (
    EXPERT_DOMAIN_CAPTION,
    EXPERT_DOMAIN_CUT,
    EXPERT_DOMAIN_MOTION,
    EXPERT_DOMAIN_STORY,
    MESSAGE_TYPE_AGREEMENT,
    MESSAGE_TYPE_CONFLICT,
    MESSAGE_TYPE_FEEDBACK,
    MESSAGE_TYPE_PROPOSAL,
    MESSAGE_TYPE_REQUEST,
)
from app.services.goal_harness import (
    all_goals_met,
    apply_rank_one_inline_fix,
    build_harness_goal_results,
    evaluate_edit_plan_goals,
    inject_harness_feedback,
    unmet_goal_issues,
)
from app.constants.harness import GOAL_RANK_ONE_EMPHASIS
from app.db import new_id, utc_now
from app.schemas import AgentMessage, ExpertProposal, MoERoutingWeights


def _candidates(blackboard: ProjectBlackboard):
    return blackboard.approved_candidates or blackboard.selected_candidates


def _build_message(
    blackboard: ProjectBlackboard,
    round_id: str,
    from_agent_id: str,
    from_agent_name: str,
    to_agent_id: str | None,
    message_type: str,
    domain: str,
    payload: dict,
) -> AgentMessage:
    return AgentMessage(
        message_id=new_id("msg"),
        project_id=blackboard.project_id,
        run_id=blackboard.run_id,
        round_id=round_id,
        from_agent_id=from_agent_id,
        from_agent_name=from_agent_name,
        to_agent_id=to_agent_id,
        message_type=message_type,
        domain=domain,
        payload=payload,
        created_at=utc_now(),
    )


def _peer_domain_messages(
    peer_messages: list[AgentMessage],
    domain: str,
) -> list[AgentMessage]:
    return [message for message in peer_messages if message.domain == domain]


class StoryAgent(BaseAgent):
    agent_id = "story_agent"
    agent_name = "Story Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        proposal, _ = await self.propose(blackboard, "direct", [], MoERoutingWeights(round_id="direct"))
        blackboard.traces[-1].metadata["hook_text"] = proposal.hook_text
        blackboard.traces[-1].metadata["outro_text"] = proposal.outro_text
        return blackboard

    async def propose(
        self,
        blackboard: ProjectBlackboard,
        round_id: str,
        peer_messages: list[AgentMessage],
        routing: MoERoutingWeights,
    ) -> tuple[ExpertProposal, list[AgentMessage]]:
        candidates = _candidates(blackboard)
        topic = blackboard.topic or "Ranking Video"
        blueprint = blackboard.reference_blueprint
        count = len(candidates)

        hook = f"Top {count} {topic}"
        outro = "Which one would you pick? Comment below."
        peer_influence: list[str] = []
        messages: list[AgentMessage] = []

        if blueprint and blueprint.hook_style:
            if "question" in blueprint.hook_style.lower():
                hook = f"Can you guess the top {topic}?"
                outro = "Did we get your #1 right?"
            elif "countdown" in blueprint.hook_style.lower():
                hook = f"Counting down the best {topic}"
                outro = "That's the list — agree or disagree?"

        cut_requests = _peer_domain_messages(peer_messages, EXPERT_DOMAIN_CUT)
        motion_requests = _peer_domain_messages(peer_messages, EXPERT_DOMAIN_MOTION)

        for cut_message in cut_requests:
            peer_influence.append(cut_message.from_agent_id)
            if cut_message.message_type == MESSAGE_TYPE_REQUEST:
                rank = cut_message.payload.get("rank")
                if rank == 1:
                    outro = "And at #1 — the one that takes it all. What do you think?"
                    messages.append(
                        _build_message(
                            blackboard,
                            round_id,
                            self.agent_id,
                            self.agent_name,
                            cut_message.from_agent_id,
                            MESSAGE_TYPE_AGREEMENT,
                            EXPERT_DOMAIN_STORY,
                            {"note": "Extended narrative emphasis for rank #1 finale"},
                        )
                    )

        for motion_message in motion_requests:
            peer_influence.append(motion_message.from_agent_id)
            if motion_message.payload.get("rank") == 1:
                hook = f"The ultimate {topic} showdown — who's #1?"
                messages.append(
                    _build_message(
                        blackboard,
                        round_id,
                        self.agent_id,
                        self.agent_name,
                        motion_message.from_agent_id,
                        MESSAGE_TYPE_AGREEMENT,
                        EXPERT_DOMAIN_STORY,
                        {"note": "Hook aligned with motion emphasis on rank #1"},
                    )
                )

        messages.append(
            _build_message(
                blackboard,
                round_id,
                self.agent_id,
                self.agent_name,
                None,
                MESSAGE_TYPE_PROPOSAL,
                EXPERT_DOMAIN_STORY,
                {"hook_text": hook, "outro_text": outro},
            )
        )
        messages.append(
            _build_message(
                blackboard,
                round_id,
                self.agent_id,
                self.agent_name,
                "caption_agent",
                MESSAGE_TYPE_REQUEST,
                EXPERT_DOMAIN_STORY,
                {"hook_text": hook, "needs_short_captions": True},
            )
        )

        proposal = ExpertProposal(
            proposal_id=new_id("prop"),
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            domain=EXPERT_DOMAIN_STORY,
            round_id=round_id,
            confidence=min(0.65 + routing.story * 0.35, 1.0),
            hook_text=hook,
            outro_text=outro,
            reasoning=f"Narrative arc for {count} ranks on '{topic}' with reference hook style alignment.",
            peer_influence=peer_influence,
        )
        return proposal, messages


class CutAgent(BaseAgent):
    agent_id = "cut_agent"
    agent_name = "Cut Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return blackboard

    async def propose(
        self,
        blackboard: ProjectBlackboard,
        round_id: str,
        peer_messages: list[AgentMessage],
        routing: MoERoutingWeights,
    ) -> tuple[ExpertProposal, list[AgentMessage]]:
        candidates = sorted(_candidates(blackboard), key=lambda item: item.recommended_rank or 99)
        blueprint = blackboard.reference_blueprint
        avg_duration = blueprint.average_item_duration_sec if blueprint else 4.0
        peer_influence: list[str] = []
        messages: list[AgentMessage] = []
        clip_adjustments: list[dict] = []
        transition_updates: list[dict] = []

        for candidate in candidates:
            rank = candidate.recommended_rank or len(clip_adjustments) + 1
            duration = candidate.duration_sec or avg_duration

            if candidate.clip_start_sec is not None and candidate.clip_end_sec is not None:
                clip_start = candidate.clip_start_sec
                clip_end = candidate.clip_end_sec
            else:
                from app.services.segment_selection_service import apply_reference_segment_to_candidate

                if blueprint:
                    segmented = apply_reference_segment_to_candidate(candidate.model_copy(deep=True), blueprint)
                    clip_start = segmented.clip_start_sec or 0.0
                    clip_end = segmented.clip_end_sec or min(duration, avg_duration + 1.0)
                else:
                    clip_start = 0.0
                    clip_end = min(duration, avg_duration + 1.0)

            if rank == 1 and blueprint and blueprint.final_rank_drama_level == "high":
                clip_end = min(duration, max(clip_end, avg_duration + 1.0))
                messages.append(
                    _build_message(
                        blackboard,
                        round_id,
                        self.agent_id,
                        self.agent_name,
                        "motion_agent",
                        MESSAGE_TYPE_REQUEST,
                        EXPERT_DOMAIN_CUT,
                        {"rank": 1, "clip_end_sec": clip_end, "needs_emphasis": True},
                    )
                )
                messages.append(
                    _build_message(
                        blackboard,
                        round_id,
                        self.agent_id,
                        self.agent_name,
                        "story_agent",
                        MESSAGE_TYPE_REQUEST,
                        EXPERT_DOMAIN_CUT,
                        {"rank": 1, "needs_finale_narrative": True},
                    )
                )
            elif rank == len(candidates):
                clip_end = max(clip_end - 0.5, 2.0)

            clip_adjustments.append(
                {
                    "rank": rank,
                    "clip_start_sec": clip_start,
                    "clip_end_sec": max(clip_end, clip_start + 1.0),
                    "candidate_id": candidate.candidate_id,
                }
            )
            transition_updates.append({"rank": rank, "type": "hard_cut"})

        story_messages = _peer_domain_messages(peer_messages, EXPERT_DOMAIN_STORY)
        for story_message in story_messages:
            peer_influence.append(story_message.from_agent_id)
            if story_message.payload.get("needs_short_captions"):
                for adjustment in clip_adjustments:
                    if adjustment["clip_end_sec"] > avg_duration + 0.5:
                        adjustment["clip_end_sec"] = max(adjustment["clip_end_sec"] - 0.3, 2.0)

        messages.append(
            _build_message(
                blackboard,
                round_id,
                self.agent_id,
                self.agent_name,
                None,
                MESSAGE_TYPE_PROPOSAL,
                EXPERT_DOMAIN_CUT,
                {"clip_count": len(clip_adjustments), "avg_duration": avg_duration},
            )
        )

        proposal = ExpertProposal(
            proposal_id=new_id("prop"),
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            domain=EXPERT_DOMAIN_CUT,
            round_id=round_id,
            confidence=min(0.60 + routing.cut * 0.40, 1.0),
            clip_adjustments=clip_adjustments,
            transition_updates=transition_updates,
            reasoning=(
                f"Cut/stitch windows follow reference blueprint "
                f"(~{avg_duration:.1f}s rank segments, hook/outro pacing preserved)."
            ),
            peer_influence=peer_influence,
        )
        return proposal, messages


class CaptionAgent(BaseAgent):
    agent_id = "caption_agent"
    agent_name = "Caption Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return blackboard

    async def propose(
        self,
        blackboard: ProjectBlackboard,
        round_id: str,
        peer_messages: list[AgentMessage],
        routing: MoERoutingWeights,
    ) -> tuple[ExpertProposal, list[AgentMessage]]:
        candidates = sorted(_candidates(blackboard), key=lambda item: item.recommended_rank or 99)
        blueprint = blackboard.reference_blueprint
        peer_influence: list[str] = []
        messages: list[AgentMessage] = []
        caption_updates: list[dict] = []

        caption_style = blueprint.caption_style if blueprint else {}
        use_uppercase = caption_style.get("case") == "upper"

        for candidate in candidates:
            rank = candidate.recommended_rank or len(caption_updates) + 1
            label = candidate.concept[:60]
            if use_uppercase:
                label = label.upper()
            caption_updates.append(
                {
                    "rank": rank,
                    "caption_text": label,
                    "label_text": label,
                    "voiceover_text": f"Number {rank}: {candidate.concept}",
                }
            )

        story_messages = _peer_domain_messages(peer_messages, EXPERT_DOMAIN_STORY)
        for story_message in story_messages:
            peer_influence.append(story_message.from_agent_id)
            hook_text = story_message.payload.get("hook_text")
            if hook_text and caption_updates:
                caption_updates[0]["caption_text"] = hook_text[:80]

        cut_messages = _peer_domain_messages(peer_messages, EXPERT_DOMAIN_CUT)
        for cut_message in cut_messages:
            peer_influence.append(cut_message.from_agent_id)
            rank = cut_message.payload.get("rank")
            if rank == 1 and cut_message.payload.get("needs_emphasis"):
                for update in caption_updates:
                    if update["rank"] == 1:
                        update["caption_text"] = f"#1 — {update['caption_text']}"

        messages.append(
            _build_message(
                blackboard,
                round_id,
                self.agent_id,
                self.agent_name,
                "motion_agent",
                MESSAGE_TYPE_FEEDBACK,
                EXPERT_DOMAIN_CAPTION,
                {"rank_1_caption": next((c["caption_text"] for c in caption_updates if c["rank"] == 1), "")},
            )
        )
        messages.append(
            _build_message(
                blackboard,
                round_id,
                self.agent_id,
                self.agent_name,
                None,
                MESSAGE_TYPE_PROPOSAL,
                EXPERT_DOMAIN_CAPTION,
                {"caption_count": len(caption_updates)},
            )
        )

        proposal = ExpertProposal(
            proposal_id=new_id("prop"),
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            domain=EXPERT_DOMAIN_CAPTION,
            round_id=round_id,
            confidence=min(0.62 + routing.caption * 0.38, 1.0),
            caption_updates=caption_updates,
            reasoning="Captions aligned to reference style with rank labels and voiceover lines.",
            peer_influence=peer_influence,
        )
        return proposal, messages


class MotionAgent(BaseAgent):
    agent_id = "motion_agent"
    agent_name = "Motion Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return blackboard

    async def propose(
        self,
        blackboard: ProjectBlackboard,
        round_id: str,
        peer_messages: list[AgentMessage],
        routing: MoERoutingWeights,
    ) -> tuple[ExpertProposal, list[AgentMessage]]:
        candidates = sorted(_candidates(blackboard), key=lambda item: item.recommended_rank or 99)
        blueprint = blackboard.reference_blueprint
        peer_influence: list[str] = []
        messages: list[AgentMessage] = []
        motion_updates: list[dict] = []
        transition_updates: list[dict] = []
        high_drama = blueprint.final_rank_drama_level == "high" if blueprint else False

        for candidate in candidates:
            rank = candidate.recommended_rank or len(motion_updates) + 1
            zoom = rank == 1
            pan = candidate.motion_energy_score > 0.6
            scale = 1.15 if rank == 1 and high_drama else 1.05 if zoom else 1.0
            motion_updates.append(
                {
                    "rank": rank,
                    "zoom": zoom,
                    "pan": pan,
                    "scale": scale,
                    "energy": candidate.motion_energy_score,
                }
            )
            transition_updates.append(
                {
                    "rank": rank,
                    "type": "zoom_cut" if rank == 1 and high_drama else "hard_cut",
                }
            )

        cut_messages = _peer_domain_messages(peer_messages, EXPERT_DOMAIN_CUT)
        for cut_message in cut_messages:
            peer_influence.append(cut_message.from_agent_id)
            if cut_message.payload.get("needs_emphasis") and cut_message.payload.get("rank") == 1:
                for update in motion_updates:
                    if update["rank"] == 1:
                        update["scale"] = 1.2
                        update["zoom"] = True
                messages.append(
                    _build_message(
                        blackboard,
                        round_id,
                        self.agent_id,
                        self.agent_name,
                        "story_agent",
                        MESSAGE_TYPE_REQUEST,
                        EXPERT_DOMAIN_MOTION,
                        {"rank": 1, "needs_hook_emphasis": True},
                    )
                )

        caption_messages = _peer_domain_messages(peer_messages, EXPERT_DOMAIN_CAPTION)
        for caption_message in caption_messages:
            peer_influence.append(caption_message.from_agent_id)
            rank_one_caption = caption_message.payload.get("rank_1_caption", "")
            if len(rank_one_caption) > 40:
                messages.append(
                    _build_message(
                        blackboard,
                        round_id,
                        self.agent_id,
                        self.agent_name,
                        "caption_agent",
                        MESSAGE_TYPE_CONFLICT,
                        EXPERT_DOMAIN_MOTION,
                        {"issue": "Rank #1 caption too long for zoom emphasis", "max_chars": 40},
                    )
                )

        messages.append(
            _build_message(
                blackboard,
                round_id,
                self.agent_id,
                self.agent_name,
                None,
                MESSAGE_TYPE_PROPOSAL,
                EXPERT_DOMAIN_MOTION,
                {"motion_count": len(motion_updates), "high_drama": high_drama},
            )
        )

        proposal = ExpertProposal(
            proposal_id=new_id("prop"),
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            domain=EXPERT_DOMAIN_MOTION,
            round_id=round_id,
            confidence=min(0.58 + routing.motion * 0.42, 1.0),
            motion_updates=motion_updates,
            transition_updates=transition_updates,
            reasoning="Motion plan with rank #1 zoom emphasis and energy-matched pan per clip.",
            peer_influence=peer_influence,
        )
        return proposal, messages


class CriticAgent(BaseAgent):
    agent_id = "critic_agent"
    agent_name = "Critic Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        evaluations = evaluate_edit_plan_goals(blackboard)

        rank_one_unmet = any(
            evaluation.goal_id == GOAL_RANK_ONE_EMPHASIS and not evaluation.met
            for evaluation in evaluations
        )
        if rank_one_unmet:
            blackboard = apply_rank_one_inline_fix(blackboard)
            evaluations = evaluate_edit_plan_goals(blackboard)

        goal_results = build_harness_goal_results(evaluations)
        issues = unmet_goal_issues(evaluations)
        goals_met = all_goals_met(evaluations)

        blackboard.harness_goal_results = goal_results
        blackboard.harness_goals_met = goals_met

        if not goals_met:
            blackboard = inject_harness_feedback(blackboard, evaluations)

        trace = blackboard.traces[-1]
        trace.metadata["critic_issues"] = issues
        trace.metadata["harness_goals_met"] = goals_met
        trace.metadata["harness_goal_results"] = [result.model_dump() for result in goal_results]
        trace.metadata["harness_revision_count"] = blackboard.harness_revision_count
        trace.metadata["moe_message_count"] = len(blackboard.agent_messages)

        if goals_met:
            trace.output_summary = (
                f"Critic verified all {len(goal_results)} harness goals — "
                f"{len(blackboard.agent_messages)} inter-agent messages"
            )
        else:
            trace.output_summary = (
                f"Critic flagged {len(issues)} unmet goal(s); "
                f"revision {blackboard.harness_revision_count}/{MAX_HARNESS_REVISIONS}"
            )
        return blackboard
