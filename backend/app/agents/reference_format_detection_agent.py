from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.constants.video_sources import (
    VIDEO_FORMAT_UNKNOWN,
    VIDEO_ORIENTATION_UNKNOWN,
    resolve_youtube_search_mode,
)
from app.services.video_format_detection import (
    detect_video_format_from_blueprint,
    detect_video_format_from_url,
    merge_format_detection_results,
    probe_youtube_video_metadata,
)


class ReferenceFormatDetectionAgent(BaseAgent):
    agent_id = "reference_format_detection"
    agent_name = "Reference Format Detection"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        reference_url = blackboard.reference_video_url
        blueprint = blackboard.reference_blueprint

        url_result = detect_video_format_from_url(reference_url)
        blueprint_result = detect_video_format_from_blueprint(
            blueprint.aspect_ratio if blueprint else None
        )
        merged = merge_format_detection_results(url_result, blueprint_result)

        if reference_url:
            probe_result = await probe_youtube_video_metadata(reference_url)
            merged = merge_format_detection_results(merged, probe_result)
            self.log_tool_call(
                blackboard,
                "yt_dlp_probe",
                {
                    "source_url": reference_url,
                    "video_format": merged.video_format,
                    "video_orientation": merged.video_orientation,
                    "width": merged.width,
                    "height": merged.height,
                    "probe_error": merged.probe_error,
                },
            )

        blackboard.target_platform = (
            "youtube_shorts"
            if merged.video_orientation == "mobile"
            else "youtube"
            if merged.video_format != VIDEO_FORMAT_UNKNOWN
            else blackboard.target_platform
        )

        trace = self.active_trace(blackboard)
        trace.input_summary = reference_url or "No reference URL — using blueprint heuristics"
        trace.output_summary = (
            f"Detected {merged.video_format} ({merged.video_orientation}, {merged.aspect_ratio_hint})"
        )
        trace.visible_reasoning = (
            f"Reference looks {'mobile/Shorts' if merged.video_orientation == 'mobile' else 'landscape/regular'}"
            if merged.video_orientation != VIDEO_ORIENTATION_UNKNOWN
            else "Could not determine orientation — defaulting to mixed YouTube search"
        )
        trace.metadata["format_detection"] = {
            "video_format": merged.video_format,
            "video_orientation": merged.video_orientation,
            "aspect_ratio_hint": merged.aspect_ratio_hint,
            "source": merged.source,
            "width": merged.width,
            "height": merged.height,
            "title": merged.title,
            "probe_error": merged.probe_error,
        }
        trace.metadata["youtube_search_mode"] = resolve_youtube_search_mode(merged.video_orientation)
        return blackboard
