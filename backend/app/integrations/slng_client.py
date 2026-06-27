import re
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.constants.slng import (
    SLNG_DEFAULT_STT_LANGUAGE,
    SLNG_DEFAULT_TTS_MODEL,
    SLNG_STT_ENDPOINT,
    SLNG_TTS_ENDPOINT,
)


def extract_transcript_from_stt_response(payload: dict[str, Any]) -> str:
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    results = payload.get("results")
    if not isinstance(results, dict):
        return ""

    channels = results.get("channels")
    if not isinstance(channels, list) or not channels:
        return ""

    alternatives = channels[0].get("alternatives")
    if not isinstance(alternatives, list) or not alternatives:
        return ""

    transcript = alternatives[0].get("transcript")
    if isinstance(transcript, str):
        return transcript.strip()
    return ""


class SLNGAudioClient:
    STT_ENDPOINT = SLNG_STT_ENDPOINT
    TTS_ENDPOINT = SLNG_TTS_ENDPOINT

    def __init__(self) -> None:
        settings = get_settings()
        settings.require_key("SLNG_API_KEY")
        self.settings = settings
        self.base_url = settings.slng_base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings.slng_api_key}"}

    async def transcribe_feedback_audio(self, audio_path: str) -> str:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            with path.open("rb") as audio_file:
                response = await client.post(
                    f"{self.base_url}{self.STT_ENDPOINT}",
                    headers=self.headers,
                    files={"audio": (path.name, audio_file, "audio/wav")},
                    data={"language": SLNG_DEFAULT_STT_LANGUAGE},
                )
            response.raise_for_status()
            payload = response.json()
            return extract_transcript_from_stt_response(payload)

    async def generate_voiceover(self, text: str, output_path: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}{self.TTS_ENDPOINT}",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"text": text, "model": SLNG_DEFAULT_TTS_MODEL},
            )
            response.raise_for_status()
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(response.content)
            return str(output)

    async def analyse_audio_style(self, video_path: str) -> dict[str, Any]:
        from app.services.audio_utils import extract_audio_from_video, measure_audio_loudness_db

        audio_path = await extract_audio_from_video(video_path)
        transcript = await self.transcribe_feedback_audio(audio_path)
        loudness = await measure_audio_loudness_db(audio_path)

        word_count = len(transcript.split())
        estimated_style = "voice_first" if word_count > 20 else "music_driven"

        result: dict[str, Any] = {
            "transcript_sample": transcript[:500],
            "has_speech": bool(transcript.strip()),
            "estimated_style": estimated_style,
            "confidence": 0.75,
            **{key: value for key, value in loudness.items() if value is not None},
        }

        mean_volume_db = loudness.get("mean_volume_db")
        if isinstance(mean_volume_db, (int, float)):
            if mean_volume_db >= -14.0:
                result["energy"] = "high"
                result["mood"] = "loud"
            elif mean_volume_db >= -22.0:
                result["energy"] = "medium"
            else:
                result["energy"] = "low"
                result["mood"] = "quiet"

        return result

    async def parse_voice_command(self, transcript: str) -> dict[str, Any]:
        lowered = transcript.lower()
        command: dict[str, Any] = {
            "raw_transcript": transcript,
            "intent": "text_feedback",
            "parameters": {},
        }

        if "replace" in lowered and re.search(r"number\s*(\d+)|#(\d+)", lowered):
            match = re.search(r"number\s*(\d+)|#(\d+)", lowered)
            command["intent"] = "replace"
            command["parameters"]["rank"] = int(match.group(1) or match.group(2))
        elif "move up" in lowered or "move down" in lowered:
            command["intent"] = "reorder"
            command["parameters"]["direction"] = "up" if "move up" in lowered else "down"
        elif "more dramatic" in lowered and ("number 1" in lowered or "#1" in lowered or "rank 1" in lowered):
            command["intent"] = "text_feedback"
            command["parameters"]["adjustment"] = "more_dramatic_rank_1"
        elif "fewer caption" in lowered or "less caption" in lowered or "reduce caption" in lowered:
            command["parameters"]["adjustment"] = "fewer_captions"
        elif "cleaner audio" in lowered or "clean audio" in lowered:
            command["parameters"]["adjustment"] = "cleaner_audio"
        elif "shorter hook" in lowered or "make the hook shorter" in lowered:
            command["parameters"]["adjustment"] = "shorter_hook"
        elif "faster" in lowered:
            command["parameters"]["adjustment"] = "faster_pacing"
        elif "slower" in lowered:
            command["parameters"]["adjustment"] = "slower_pacing"
        elif "approve" in lowered:
            command["intent"] = "approve"

        return command
