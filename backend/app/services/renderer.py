from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas import EditPlan
from app.services.video_utils import (
    add_text_overlay,
    concat_videos,
    get_video_duration,
    scale_to_vertical,
    trim_clip,
)


class VideoRenderer:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def render(self, edit_plan: EditPlan, voiceover_path: str | None = None) -> str:
        project_dir = self.settings.output_dir / edit_plan.project_id / "render"
        project_dir.mkdir(parents=True, exist_ok=True)

        processed_clips: list[str] = []
        for index, section in enumerate(edit_plan.sections):
            clip_dir = project_dir / f"clip_{index}"
            clip_dir.mkdir(parents=True, exist_ok=True)
            trimmed = str(clip_dir / "trimmed.mp4")
            scaled = str(clip_dir / "scaled.mp4")
            labeled = str(clip_dir / "labeled.mp4")

            await trim_clip(
                section.source_file_path,
                trimmed,
                section.clip_start_sec,
                section.clip_end_sec,
            )
            await scale_to_vertical(trimmed, scaled)
            await add_text_overlay(
                scaled,
                labeled,
                f"#{section.rank} {section.label_text}",
                start_sec=0.0,
                duration_sec=min(2.5, section.clip_end_sec - section.clip_start_sec),
            )
            processed_clips.append(labeled)

        concat_path = str(project_dir / "concat.mp4")
        await concat_videos(processed_clips, concat_path)

        with_hook = str(project_dir / "with_hook.mp4")
        await add_text_overlay(
            concat_path,
            with_hook,
            edit_plan.hook_text,
            start_sec=0.0,
            duration_sec=min(3.0, edit_plan.output_duration_sec * 0.15),
        )

        output_path = str(
            self.settings.output_dir
            / edit_plan.project_id
            / f"{edit_plan.project_id}_v{edit_plan.version}.mp4"
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if voiceover_path and Path(voiceover_path).exists():
            from app.services.video_utils import run_ffmpeg_command

            await run_ffmpeg_command(
                [
                    "-i",
                    with_hook,
                    "-i",
                    voiceover_path,
                    "-filter_complex",
                    "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                    "-map",
                    "0:v",
                    "-map",
                    "[aout]",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    output_path,
                ]
            )
        else:
            from shutil import copy2

            copy2(with_hook, output_path)

        duration = await get_video_duration(output_path)
        edit_plan.output_duration_sec = duration
        return output_path
