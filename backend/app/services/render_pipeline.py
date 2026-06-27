from pathlib import Path
from shutil import copy2

from app.config import get_settings
from app.schemas import EditPlan, RankedClip
from app.services.reference_audio_plan_service import build_audio_mix_filter
from app.services.video_utils import (
    add_text_overlay,
    concat_videos,
    get_video_duration,
    run_ffmpeg_command,
    scale_to_vertical,
    trim_clip,
)


def render_project_dir(project_id: str, version: int) -> Path:
    settings = get_settings()
    project_dir = settings.output_dir / project_id / "render" / f"v{version}"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


async def render_rank_clip(
    section: RankedClip,
    index: int,
    project_dir: Path,
    caption_font_size: int = 48,
) -> str:
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
    overlay_text = section.caption_text or section.label_text
    await add_text_overlay(
        scaled,
        labeled,
        overlay_text,
        start_sec=0.0,
        duration_sec=min(2.5, section.clip_end_sec - section.clip_start_sec),
        font_size=caption_font_size,
    )
    return labeled


async def stitch_rank_clips(processed_clips: list[str], project_dir: Path) -> str:
    concat_path = str(project_dir / "concat.mp4")
    await concat_videos(processed_clips, concat_path)
    return concat_path


async def apply_hook_overlay(
    source_path: str,
    hook_text: str,
    output_duration_sec: float,
    project_dir: Path,
    caption_font_size: int = 48,
) -> str:
    with_hook = str(project_dir / "with_hook.mp4")
    await add_text_overlay(
        source_path,
        with_hook,
        hook_text,
        start_sec=0.0,
        duration_sec=min(3.0, output_duration_sec * 0.15),
        font_size=caption_font_size,
    )
    return with_hook


async def finalize_render_output(
    *,
    source_path: str,
    voiceover_path: str | None,
    project_id: str,
    version: int,
    audio_plan: dict[str, object] | None = None,
) -> str:
    settings = get_settings()
    output_path = str(settings.output_dir / project_id / f"{project_id}_v{version}.mp4")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if voiceover_path and Path(voiceover_path).exists():
        mix_filter = build_audio_mix_filter(audio_plan or {})
        await run_ffmpeg_command(
            [
                "-i",
                source_path,
                "-i",
                voiceover_path,
                "-filter_complex",
                mix_filter,
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
        copy2(source_path, output_path)

    return output_path


async def render_edit_plan(edit_plan: EditPlan, voiceover_path: str | None = None) -> str:
    project_dir = render_project_dir(edit_plan.project_id, edit_plan.version)
    render_settings = edit_plan.render_settings if isinstance(edit_plan.render_settings, dict) else {}
    caption_font_size = int(render_settings.get("caption_font_size") or 48)
    processed_clips: list[str] = []
    for index, section in enumerate(edit_plan.sections):
        processed_clips.append(
            await render_rank_clip(section, index, project_dir, caption_font_size=caption_font_size)
        )

    concat_path = await stitch_rank_clips(processed_clips, project_dir)
    with_hook = await apply_hook_overlay(
        concat_path,
        edit_plan.hook_text,
        edit_plan.output_duration_sec,
        project_dir,
        caption_font_size=caption_font_size,
    )
    output_path = await finalize_render_output(
        source_path=with_hook,
        voiceover_path=voiceover_path,
        project_id=edit_plan.project_id,
        version=edit_plan.version,
        audio_plan=edit_plan.audio_plan,
    )
    duration = await get_video_duration(output_path)
    edit_plan.output_duration_sec = duration
    return output_path
