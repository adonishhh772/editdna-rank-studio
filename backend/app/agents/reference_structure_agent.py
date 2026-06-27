from pathlib import Path

from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.db import new_id
from app.integrations.gemini_client import GeminiVideoClient


class ReferenceStructureAgent(BaseAgent):
    agent_id = "reference_structure_analysis"
    agent_name = "Structure & Pacing Analysis"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        has_local = bool(blackboard.reference_video_path)
        has_url = bool(blackboard.reference_video_url)
        if not has_local and not has_url:
            raise RuntimeError("Reference video path or URL is required")

        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "reference_analyst.md"
        prompt = prompt_path.read_text(encoding="utf-8")
        prompt += (
            "\nFocus this pass on: hook timing, ranking flow, section order, pacing, "
            "caption style, transitions, rank reveal, and outro structure.\n"
            f"project_id={blackboard.project_id}\nblueprint_id={new_id('bp')}"
        )

        gemini = GeminiVideoClient()
        blueprint = await gemini.analyse_reference_video(
            prompt=prompt,
            video_path=blackboard.reference_video_path if has_local else None,
            video_url=blackboard.reference_video_url if not has_local else None,
        )

        probe = blackboard.memory_context.get("reference_probe_metadata", {})
        if isinstance(probe, dict):
            probe_duration = probe.get("duration_sec")
            if isinstance(probe_duration, (int, float)) and probe_duration > 0:
                blueprint.duration_sec = float(probe_duration)

        blackboard.reference_blueprint = blueprint
        blackboard.memory_context["_reference_structure_summary"] = {
            "ranking_count": blueprint.ranking_count,
            "hook_duration_sec": blueprint.hook_duration_sec,
            "average_item_duration_sec": blueprint.average_item_duration_sec,
            "rank_reveal_style": blueprint.rank_reveal_style,
        }

        trace = self.active_trace(blackboard)
        trace.input_summary = "Analysing hook, ranking flow, and pacing grammar"
        trace.output_summary = (
            f"{blueprint.ranking_count} ranks · hook {blueprint.hook_duration_sec}s · "
            f"~{blueprint.average_item_duration_sec}s per item"
        )
        trace.visible_reasoning = (
            "Extracted editing structure: hook style, rank order, segment timing, and reveal pattern."
        )
        self.log_tool_call(
            blackboard,
            "gemini_reference_structure",
            {
                "ranking_count": blueprint.ranking_count,
                "hook_duration_sec": blueprint.hook_duration_sec,
                "confidence": blueprint.confidence,
            },
        )
        return blackboard
