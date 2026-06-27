from pathlib import Path

from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.schemas import CandidateVideo
from app.services.segment_selection_service import apply_reference_segment_to_candidate
from app.services.video_utils import generate_thumbnail, get_video_duration


class CandidateSegmentAgent(BaseAgent):
    agent_id = "candidate_segment_analysis"
    agent_name = "Highlight Segment Selection"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        draft_raw = blackboard.memory_context.get("_candidate_analysis_draft")
        if not draft_raw:
            raise RuntimeError("Visual analysis must run before segment selection")

        analyzed = CandidateVideo.model_validate(draft_raw)
        if not analyzed.local_file_path or not Path(analyzed.local_file_path).exists():
            raise RuntimeError("Downloaded video file is missing")

        analyzed.duration_sec = await get_video_duration(analyzed.local_file_path)
        if blackboard.reference_blueprint:
            analyzed = apply_reference_segment_to_candidate(analyzed, blackboard.reference_blueprint)

        blackboard.memory_context["_candidate_analysis_draft"] = analyzed.model_dump()

        trace = self.active_trace(blackboard)
        if analyzed.clip_start_sec is not None and analyzed.clip_end_sec is not None:
            trace.input_summary = "Choosing stitch-ready highlight window from reference blueprint"
            trace.output_summary = (
                f"Highlight {analyzed.clip_start_sec:.1f}–{analyzed.clip_end_sec:.1f}s"
            )
            trace.visible_reasoning = analyzed.highlight_reason or (
                "Aligned highlight segment to reference rank slot duration and reveal pattern."
            )
        else:
            trace.output_summary = "Using full source clip"
            trace.visible_reasoning = "Source is already short enough to use end-to-end."

        self.log_tool_call(
            blackboard,
            "segment_selection",
            {
                "clip_start_sec": analyzed.clip_start_sec,
                "clip_end_sec": analyzed.clip_end_sec,
                "duration_sec": analyzed.duration_sec,
            },
        )
        return blackboard


class CandidatePreviewAgent(BaseAgent):
    agent_id = "candidate_preview"
    agent_name = "Preview Thumbnail"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        draft_raw = blackboard.memory_context.get("_candidate_analysis_draft")
        if not draft_raw:
            raise RuntimeError("Segment analysis must run before preview generation")

        analyzed = CandidateVideo.model_validate(draft_raw)
        if not analyzed.local_file_path:
            blackboard.memory_context["_candidate_analysis_result"] = analyzed.model_dump()
            return blackboard

        thumb_at_sec = analyzed.clip_start_sec or 1.0
        thumb_path = str(Path(analyzed.local_file_path).with_suffix(".thumb.jpg"))
        try:
            await generate_thumbnail(analyzed.local_file_path, thumb_path, at_sec=thumb_at_sec)
            analyzed.thumbnail_path = thumb_path
        except Exception:
            pass

        blackboard.memory_context["_candidate_analysis_result"] = analyzed.model_dump()
        blackboard.memory_context.pop("_candidate_analysis_draft", None)

        trace = self.active_trace(blackboard)
        trace.input_summary = "Generating review thumbnail at highlight frame"
        trace.output_summary = "Preview ready for human approval"
        trace.visible_reasoning = f"Thumbnail captured at {thumb_at_sec:.1f}s for quick review."
        return blackboard
