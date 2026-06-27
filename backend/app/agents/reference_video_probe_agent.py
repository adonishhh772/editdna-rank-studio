from pathlib import Path

from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.services.reference_media_service import ensure_reference_local_path
from app.services.video_format_detection import (
    detect_video_format_from_url,
    merge_format_detection_results,
    probe_platform_video_metadata,
)
from app.services.video_utils import get_video_dimensions, get_video_duration


class ReferenceVideoProbeAgent(BaseAgent):
    agent_id = "reference_video_probe"
    agent_name = "Reference Video Probe"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        probe_metadata: dict[str, object] = {
            "source": "none",
            "duration_sec": None,
            "width": None,
            "height": None,
            "video_orientation": "unknown",
            "aspect_ratio_hint": "unknown",
        }

        if blackboard.reference_video_path and Path(blackboard.reference_video_path).exists():
            local_path = blackboard.reference_video_path
            duration_sec = await get_video_duration(local_path)
            width, height = await get_video_dimensions(local_path)
            orientation = "mobile" if height and width and height > width else "landscape"
            probe_metadata = {
                "source": "local_probe",
                "duration_sec": duration_sec,
                "width": width,
                "height": height,
                "video_orientation": orientation,
                "aspect_ratio_hint": "9:16" if orientation == "mobile" else "16:9",
            }
            self.log_tool_call(
                blackboard,
                "ffprobe",
                {
                    "local_file_path": local_path,
                    "duration_sec": duration_sec,
                    "width": width,
                    "height": height,
                },
            )
        elif blackboard.reference_video_url:
            local_path = await ensure_reference_local_path(
                project_id=blackboard.project_id,
                reference_video_path=blackboard.reference_video_path,
                reference_video_url=blackboard.reference_video_url,
            )
            if local_path:
                blackboard.reference_video_path = local_path
                duration_sec = await get_video_duration(local_path)
                width, height = await get_video_dimensions(local_path)
                orientation = "mobile" if height and width and height > width else "landscape"
                probe_metadata = {
                    "source": "local_download",
                    "duration_sec": duration_sec,
                    "width": width,
                    "height": height,
                    "video_orientation": orientation,
                    "aspect_ratio_hint": "9:16" if orientation == "mobile" else "16:9",
                }
                self.log_tool_call(
                    blackboard,
                    "yt_dlp_download",
                    {
                        "source_url": blackboard.reference_video_url,
                        "local_file_path": local_path,
                        **probe_metadata,
                    },
                )
            else:
                url_result = detect_video_format_from_url(blackboard.reference_video_url)
                probe_result = await probe_platform_video_metadata(blackboard.reference_video_url)
                merged = merge_format_detection_results(url_result, probe_result)
                probe_metadata = {
                    "source": merged.source,
                    "duration_sec": merged.duration_sec,
                    "width": merged.width,
                    "height": merged.height,
                    "video_orientation": merged.video_orientation,
                    "aspect_ratio_hint": merged.aspect_ratio_hint,
                    "title": merged.title,
                }
                self.log_tool_call(
                    blackboard,
                    "yt_dlp_probe",
                    {
                        "source_url": blackboard.reference_video_url,
                        **probe_metadata,
                    },
                )

        blackboard.memory_context["reference_probe_metadata"] = probe_metadata
        trace = self.active_trace(blackboard)
        duration = probe_metadata.get("duration_sec")
        orientation = probe_metadata.get("video_orientation")
        trace.input_summary = "Probing reference video duration and aspect"
        trace.output_summary = (
            f"{duration:.0f}s {orientation} clip"
            if isinstance(duration, (int, float))
            else f"Format: {orientation}"
        )
        trace.visible_reasoning = (
            "Measured reference duration, resolution, and vertical vs landscape orientation."
        )
        return blackboard
