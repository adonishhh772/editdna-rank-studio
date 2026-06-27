from app.agents.base import BaseAgent
from app.agents.moe_bus import MoEBus
from app.blackboard import ProjectBlackboard
from app.constants.moe import (
    EXPERT_DOMAIN_CAPTION,
    EXPERT_DOMAIN_CUT,
    EXPERT_DOMAIN_MOTION,
    EXPERT_DOMAIN_STORY,
)
from app.db import new_id
from app.schemas import MoEFusionResult


class FusionAgent(BaseAgent):
    agent_id = "fusion_agent"
    agent_name = "MoE Fusion Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        routing = blackboard.moe_routing
        if routing is None:
            raise RuntimeError("MoE routing weights are required before fusion")

        latest = MoEBus.get_latest_proposals_by_domain(blackboard.expert_proposals)
        story = latest.get(EXPERT_DOMAIN_STORY)
        cut = latest.get(EXPERT_DOMAIN_CUT)
        caption = latest.get(EXPERT_DOMAIN_CAPTION)
        motion = latest.get(EXPERT_DOMAIN_MOTION)

        candidates = blackboard.approved_candidates or blackboard.selected_candidates
        default_hook = f"Top {len(candidates)} {blackboard.topic or 'Picks'}"
        default_outro = "Which one wins for you?"

        hook_candidates: list[tuple[str, float]] = []
        outro_candidates: list[tuple[str, float]] = []
        clip_lists: list[list[dict]] = []
        clip_weights: list[float] = []
        caption_lists: list[list[dict]] = []
        caption_weights: list[float] = []
        motion_lists: list[list[dict]] = []
        motion_weights: list[float] = []
        transition_lists: list[list[dict]] = []
        transition_weights: list[float] = []
        contributions: dict[str, float] = {}
        consensus_notes: list[str] = []

        if story:
            if story.hook_text:
                hook_candidates.append((story.hook_text, routing.story * story.confidence))
            if story.outro_text:
                outro_candidates.append((story.outro_text, routing.story * story.confidence))
            contributions[story.agent_id] = routing.story * story.confidence
            consensus_notes.append(f"Story: {story.reasoning}")

        if cut:
            clip_lists.append(cut.clip_adjustments)
            clip_weights.append(routing.cut * cut.confidence)
            transition_lists.append(cut.transition_updates)
            transition_weights.append(routing.cut * cut.confidence)
            contributions[cut.agent_id] = routing.cut * cut.confidence
            consensus_notes.append(f"Cut: {cut.reasoning}")

        if caption:
            caption_lists.append(caption.caption_updates)
            caption_weights.append(routing.caption * caption.confidence)
            if caption.hook_text:
                hook_candidates.append((caption.hook_text, routing.caption * caption.confidence * 0.5))
            contributions[caption.agent_id] = routing.caption * caption.confidence
            consensus_notes.append(f"Caption: {caption.reasoning}")

        if motion:
            motion_lists.append(motion.motion_updates)
            motion_weights.append(routing.motion * motion.confidence)
            transition_lists.append(motion.transition_updates)
            transition_weights.append(routing.motion * motion.confidence * 0.5)
            contributions[motion.agent_id] = routing.motion * motion.confidence
            consensus_notes.append(f"Motion: {motion.reasoning}")

        fusion = MoEFusionResult(
            fusion_id=new_id("fusion"),
            round_id=routing.round_id,
            hook_text=MoEBus.weighted_pick_string(hook_candidates, default_hook),
            outro_text=MoEBus.weighted_pick_string(outro_candidates, default_outro),
            clip_adjustments=MoEBus.merge_ranked_updates(clip_lists, clip_weights),
            caption_updates=MoEBus.merge_ranked_updates(caption_lists, caption_weights),
            motion_updates=MoEBus.merge_ranked_updates(motion_lists, motion_weights),
            transition_updates=MoEBus.merge_ranked_updates(transition_lists, transition_weights),
            routing_weights=routing,
            expert_contributions=contributions,
            consensus_notes=consensus_notes,
        )

        blackboard.moe_fusion = fusion
        trace = self.active_trace(blackboard)
        trace.output_summary = (
            f"Fused {len(latest)} expert proposals with weighted MoE routing"
        )
        trace.visible_reasoning = routing.reasoning
        trace.metadata["fusion"] = fusion.model_dump()
        trace.metadata["expert_weights"] = {
            "story": routing.story,
            "cut": routing.cut,
            "caption": routing.caption,
            "motion": routing.motion,
        }
        return blackboard
