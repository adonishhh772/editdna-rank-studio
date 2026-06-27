from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.schemas import CandidateVideo


class CandidateVisualAnalysisAgent(BaseAgent):
    agent_id = "candidate_visual_analysis"
    agent_name = "Visual & Topic Analysis"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        from pathlib import Path

        from app.integrations.gemini_client import GeminiVideoClient

        request = blackboard.memory_context.get("_candidate_analysis_request", {})
        candidate = CandidateVideo.model_validate(request)
        if not blackboard.reference_blueprint:
            raise RuntimeError("Reference blueprint is required")
        if not candidate.local_file_path or not Path(candidate.local_file_path).exists():
            raise RuntimeError("Downloaded video file is missing")

        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "candidate_analysis.md"
        prompt = prompt_path.read_text(encoding="utf-8")
        prompt += (
            "\nFocus this pass on: topic relevance, visual quality, motion energy, "
            "text overlays, reference style fit, and the best highlight window inside the clip.\n"
        )

        gemini = GeminiVideoClient()
        analyzed = await gemini.analyse_candidate_video(
            topic=blackboard.topic or "",
            reference_blueprint=blackboard.reference_blueprint,
            memory_context=blackboard.memory_context,
            prompt=prompt,
            candidate_id=candidate.candidate_id,
            project_id=blackboard.project_id,
            video_path=candidate.local_file_path,
            video_url=None,
        )
        analyzed.candidate_id = candidate.candidate_id
        analyzed.project_id = blackboard.project_id
        analyzed.local_file_path = candidate.local_file_path
        analyzed.source_url = candidate.source_url
        analyzed.source_type = candidate.source_type
        analyzed.concept = candidate.concept
        analyzed.recommended_rank = candidate.recommended_rank
        analyzed.status = "selected"

        blackboard.memory_context["_candidate_analysis_draft"] = analyzed.model_dump()

        trace = self.active_trace(blackboard)
        trace.input_summary = f"Scoring visuals and topic fit for '{candidate.concept}'"
        trace.output_summary = (
            f"Style {analyzed.reference_style_fit_score:.0%} · "
            f"Topic {analyzed.topic_match_score:.0%} · "
            f"Motion {analyzed.motion_energy_score:.0%}"
        )
        trace.visible_reasoning = (
            "Gemini scored topic match, visual quality, motion, text relevance, and reference style fit."
        )
        self.log_tool_call(
            blackboard,
            "gemini_candidate_visual",
            {
                "reference_style_fit_score": analyzed.reference_style_fit_score,
                "topic_match_score": analyzed.topic_match_score,
                "clip_start_sec": analyzed.clip_start_sec,
                "clip_end_sec": analyzed.clip_end_sec,
            },
        )
        return blackboard
