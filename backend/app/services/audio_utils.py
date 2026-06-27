import asyncio
from pathlib import Path

from app.services.video_utils import run_ffmpeg_command


async def extract_audio_from_video(video_path: str, output_path: str | None = None) -> str:
    source = Path(video_path)
    target = Path(output_path) if output_path else source.with_suffix(".wav")

    await run_ffmpeg_command(
        [
            "-i",
            str(source),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(target),
        ]
    )
    return str(target)
