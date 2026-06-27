import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any


async def run_ffmpeg_command(args: list[str]) -> None:
    def execute() -> None:
        result = subprocess.run(
            ["ffmpeg", "-y", *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or "FFmpeg command failed")

    await asyncio.to_thread(execute)


async def get_video_dimensions(video_path: str) -> tuple[int | None, int | None]:
    def probe() -> tuple[int | None, int | None]:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None, None
        try:
            payload = json.loads(result.stdout)
            streams = payload.get("streams") or []
            if not streams:
                return None, None
            stream = streams[0]
            width = stream.get("width")
            height = stream.get("height")
            return (
                int(width) if isinstance(width, (int, float)) else None,
                int(height) if isinstance(height, (int, float)) else None,
            )
        except (json.JSONDecodeError, IndexError, TypeError):
            return None, None

    return await asyncio.to_thread(probe)


async def get_video_duration(video_path: str) -> float:
    def probe() -> float:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return 0.0
        return float(result.stdout.strip() or 0.0)

    return await asyncio.to_thread(probe)


async def generate_thumbnail(video_path: str, output_path: str, at_sec: float = 1.0) -> str:
    await run_ffmpeg_command(
        [
            "-ss",
            str(at_sec),
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            output_path,
        ]
    )
    return output_path


async def trim_clip(
    source_path: str,
    output_path: str,
    start_sec: float,
    end_sec: float,
) -> str:
    duration = max(end_sec - start_sec, 0.5)
    await run_ffmpeg_command(
        [
            "-ss",
            str(start_sec),
            "-i",
            source_path,
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            output_path,
        ]
    )
    return output_path


async def scale_to_vertical(source_path: str, output_path: str, width: int = 1080, height: int = 1920) -> str:
    await run_ffmpeg_command(
        [
            "-i",
            source_path,
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            output_path,
        ]
    )
    return output_path


async def concat_videos(input_paths: list[str], output_path: str) -> str:
    list_file = Path(output_path).with_suffix(".txt")
    lines = [f"file '{Path(path).resolve()}'" for path in input_paths]
    list_file.write_text("\n".join(lines), encoding="utf-8")
    await run_ffmpeg_command(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            output_path,
        ]
    )
    list_file.unlink(missing_ok=True)
    return output_path


async def add_text_overlay(
    source_path: str,
    output_path: str,
    text: str,
    start_sec: float = 0.0,
    duration_sec: float = 2.0,
) -> str:
    escaped = text.replace(":", "\\:").replace("'", "\\'")
    drawtext = (
        f"drawtext=text='{escaped}':fontsize=48:fontcolor=white:"
        f"x=(w-text_w)/2:y=120:box=1:boxcolor=black@0.5:enable='between(t,{start_sec},{start_sec + duration_sec})'"
    )
    await run_ffmpeg_command(
        [
            "-i",
            source_path,
            "-vf",
            drawtext,
            "-c:a",
            "copy",
            output_path,
        ]
    )
    return output_path
