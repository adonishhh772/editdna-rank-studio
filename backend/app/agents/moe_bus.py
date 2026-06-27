import asyncio
from copy import deepcopy
from typing import Any, Protocol

from app.blackboard import ProjectBlackboard
from app.constants.moe import (
    MESSAGE_TYPE_ROUTING,
    MOE_ROUND_FUSE,
    MOE_ROUND_PROPOSE,
    MOE_ROUND_REFINE,
)
from app.db import new_id, save_blackboard, utc_now
from app.schemas import AgentMessage, ExpertProposal, MoERoutingWeights


class MoEExpert(Protocol):
    agent_id: str
    agent_name: str

    async def propose(
        self,
        blackboard: ProjectBlackboard,
        round_id: str,
        peer_messages: list[AgentMessage],
        routing: MoERoutingWeights,
    ) -> tuple[ExpertProposal, list[AgentMessage]]: ...


def compute_routing_weights(blackboard: ProjectBlackboard, round_id: str) -> MoERoutingWeights:
    blueprint = blackboard.reference_blueprint
    story_weight = 0.25
    cut_weight = 0.25
    caption_weight = 0.25
    motion_weight = 0.25
    reasoning_parts: list[str] = ["Balanced MoE routing for ranking edit plan."]

    if blueprint:
        caption_style = blueprint.caption_style or {}
        if caption_style.get("prominence") == "high" or blueprint.hook_style == "text_heavy":
            caption_weight += 0.10
            story_weight -= 0.05
            cut_weight -= 0.05
            reasoning_parts.append("Caption expert boosted for text-heavy reference.")

        if blueprint.final_rank_drama_level == "high":
            motion_weight += 0.12
            cut_weight += 0.05
            story_weight -= 0.08
            caption_weight -= 0.09
            reasoning_parts.append("Motion + cut experts boosted for high drama finale.")

        pacing = blueprint.pacing_style or {}
        if pacing.get("tempo") == "fast":
            cut_weight += 0.08
            motion_weight += 0.04
            story_weight -= 0.06
            caption_weight -= 0.06
            reasoning_parts.append("Cut expert boosted for fast pacing reference.")

        if blueprint.motion_style.get("energy") == "high":
            motion_weight += 0.08
            cut_weight -= 0.04
            caption_weight -= 0.04
            reasoning_parts.append("Motion expert boosted for high-energy reference.")

    memory_text = str(blackboard.memory_context.get("final_answer", "")).lower()
    if "dramatic" in memory_text:
        motion_weight += 0.06
        cut_weight += 0.04
        caption_weight -= 0.05
        story_weight -= 0.05
        reasoning_parts.append("Memory prefers dramatic emphasis → motion/cut upweighted.")

    if "faster" in memory_text:
        cut_weight += 0.08
        motion_weight += 0.02
        story_weight -= 0.05
        caption_weight -= 0.05
        reasoning_parts.append("Memory prefers faster pacing → cut upweighted.")

    total = story_weight + cut_weight + caption_weight + motion_weight
    return MoERoutingWeights(
        round_id=round_id,
        story=story_weight / total,
        cut=cut_weight / total,
        caption=caption_weight / total,
        motion=motion_weight / total,
        reasoning=" ".join(reasoning_parts),
    )


def _messages_for_agent(
    messages: list[AgentMessage],
    agent_id: str,
) -> list[AgentMessage]:
    return [
        message
        for message in messages
        if message.to_agent_id is None or message.to_agent_id == agent_id
    ]


class MoEBus:
    async def run_parallel_round(
        self,
        experts: list[MoEExpert],
        blackboard: ProjectBlackboard,
        round_id: str,
        round_label: str,
        peer_messages: list[AgentMessage],
        routing: MoERoutingWeights,
    ) -> tuple[list[ExpertProposal], list[AgentMessage]]:
        snapshot = deepcopy(blackboard)

        async def run_single_expert(expert: MoEExpert) -> tuple[ExpertProposal, list[AgentMessage]]:
            agent_peer_messages = _messages_for_agent(peer_messages, expert.agent_id)
            return await expert.propose(snapshot, round_id, agent_peer_messages, routing)

        results = await asyncio.gather(*[run_single_expert(expert) for expert in experts])
        proposals: list[ExpertProposal] = []
        new_messages: list[AgentMessage] = []
        for proposal, messages in results:
            proposals.append(proposal)
            new_messages.extend(messages)

        blackboard.expert_proposals.extend(proposals)
        blackboard.agent_messages.extend(new_messages)
        save_blackboard(blackboard)
        return proposals, new_messages

    async def run_moe_pipeline(
        self,
        experts: list[MoEExpert],
        blackboard: ProjectBlackboard,
    ) -> ProjectBlackboard:
        round_id = new_id("moe")
        routing = compute_routing_weights(blackboard, round_id)
        blackboard.moe_routing = routing

        routing_message = AgentMessage(
            message_id=new_id("msg"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            round_id=round_id,
            from_agent_id="moe_router",
            from_agent_name="MoE Router",
            to_agent_id=None,
            message_type=MESSAGE_TYPE_ROUTING,
            domain="routing",
            payload={
                "weights": routing.model_dump(),
                "round": MOE_ROUND_PROPOSE,
            },
            created_at=utc_now(),
        )
        blackboard.agent_messages.append(routing_message)
        save_blackboard(blackboard)

        propose_round_id = f"{round_id}-{MOE_ROUND_PROPOSE}"
        _, round_one_messages = await self.run_parallel_round(
            experts,
            blackboard,
            propose_round_id,
            MOE_ROUND_PROPOSE,
            peer_messages=[],
            routing=routing,
        )

        refine_round_id = f"{round_id}-{MOE_ROUND_REFINE}"
        await self.run_parallel_round(
            experts,
            blackboard,
            refine_round_id,
            MOE_ROUND_REFINE,
            peer_messages=round_one_messages,
            routing=routing,
        )

        blackboard.stage = f"moe_{MOE_ROUND_FUSE}"
        save_blackboard(blackboard)
        return blackboard

    @staticmethod
    def get_latest_proposals_by_domain(
        proposals: list[ExpertProposal],
    ) -> dict[str, ExpertProposal]:
        latest: dict[str, ExpertProposal] = {}
        for proposal in proposals:
            existing = latest.get(proposal.domain)
            if existing is None or proposal.round_id > existing.round_id:
                latest[proposal.domain] = proposal
        return latest

    @staticmethod
    def weighted_pick_string(
        candidates: list[tuple[str, float]],
        fallback: str,
    ) -> str:
        if not candidates:
            return fallback
        best_text, _ = max(candidates, key=lambda item: item[1])
        return best_text or fallback

    @staticmethod
    def merge_ranked_updates(
        updates_list: list[list[dict[str, Any]]],
        weights: list[float],
    ) -> list[dict[str, Any]]:
        merged: dict[int, dict[str, Any]] = {}
        weight_sums: dict[int, float] = {}

        for updates, weight in zip(updates_list, weights):
            for update in updates:
                rank = int(update.get("rank", 0))
                if rank <= 0:
                    continue
                if rank not in merged:
                    merged[rank] = {"rank": rank}
                    weight_sums[rank] = 0.0
                weight_sums[rank] += weight
                for key, value in update.items():
                    if key == "rank":
                        continue
                    if isinstance(value, (int, float)):
                        merged[rank][key] = merged[rank].get(key, 0.0) + value * weight
                    elif key not in merged[rank]:
                        merged[rank][key] = value

        result: list[dict[str, Any]] = []
        for rank in sorted(merged.keys()):
            entry = merged[rank]
            total_weight = weight_sums.get(rank, 1.0) or 1.0
            for key, value in list(entry.items()):
                if isinstance(value, float) and key.endswith("_sec"):
                    entry[key] = round(value / total_weight, 2)
            result.append(entry)
        return result
