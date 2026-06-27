import asyncio
import logging
import re
import shutil
from pathlib import Path

from app.services.video_utils import run_ffmpeg_command

logger = logging.getLogger(__name__)

MEAN_VOLUME_PATTERN = re.compile(r"mean_volume:\s*([-\d.]+)\s*dB")
MAX_VOLUME_PATTERN = re.compile(r"max_volume:\s*([-\d.]+)\s*dB")


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


async def measure_audio_loudness_db(audio_path: str) -> dict[str, float | None]:
    source = Path(audio_path)
    if not source.exists():
        return {"mean_volume_db": None, "max_volume_db": None}

    def probe_loudness() -> dict[str, float | None]:
        import subprocess

        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(source),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        stderr = result.stderr or ""
        mean_match = MEAN_VOLUME_PATTERN.search(stderr)
        max_match = MAX_VOLUME_PATTERN.search(stderr)
        mean_volume_db = float(mean_match.group(1)) if mean_match else None
        max_volume_db = float(max_match.group(1)) if max_match else None
        return {"mean_volume_db": mean_volume_db, "max_volume_db": max_volume_db}

    return await asyncio.to_thread(probe_loudness)


async def apply_audio_gain_db(input_path: str, output_path: str, gain_db: float) -> str:
    if abs(gain_db) < 0.1:
        if input_path != output_path:
            await asyncio.to_thread(shutil.copy2, input_path, output_path)
        return output_path

    await run_ffmpeg_command(
        [
            "-i",
            input_path,
            "-af",
            f"volume={gain_db:.2f}dB",
            output_path,
        ]
    )
    return output_path
