import asyncio
import json
import time
from pathlib import Path
from typing import Any, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.services.preference_learning_service import format_video_preferences_for_analysis
from app.constants.video_sources import is_single_youtube_video_url
from app.schemas import CandidateVideo, ReferenceBlueprint

T = TypeVar("T", bound=BaseModel)


class GeminiVideoClient:
    def __init__(self) -> None:
        settings = get_settings()
        settings.require_key("GEMINI_API_KEY")
        self.settings = settings
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def upload_video(self, file_path: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._upload_video_sync, file_path)

    def _upload_video_sync(self, file_path: str) -> dict[str, Any]:
        uploaded = self.client.files.upload(file=file_path)
        return {
            "name": uploaded.name,
            "uri": uploaded.uri,
            "mime_type": uploaded.mime_type,
            "state": uploaded.state.name if uploaded.state else "UNKNOWN",
        }

    async def wait_until_active(self, uploaded_file: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._wait_until_active_sync, uploaded_file)

    def _wait_until_active_sync(self, uploaded_file: dict[str, Any]) -> dict[str, Any]:
        current = uploaded_file
        for _ in range(120):
            file_obj = self.client.files.get(name=current["name"])
            state_name = file_obj.state.name if file_obj.state else "UNKNOWN"
            current = {
                "name": file_obj.name,
                "uri": file_obj.uri,
                "mime_type": file_obj.mime_type,
                "state": state_name,
            }
            if state_name == "ACTIVE":
                return current
            if state_name == "FAILED":
                raise RuntimeError("Gemini video processing failed")
            time.sleep(5)
        raise TimeoutError("Timed out waiting for Gemini video to become ACTIVE")

    async def analyse_reference_video(
        self,
        prompt: str,
        video_path: str | None = None,
        video_url: str | None = None,
    ) -> ReferenceBlueprint:
        if video_path:
            uploaded = await self.upload_video(video_path)
            active = await self.wait_until_active(uploaded)
            return await self.generate_json_from_video(
                active_file=active,
                prompt=prompt,
                schema=ReferenceBlueprint,
                model=self.settings.gemini_reference_model,
            )

        if video_url:
            return await self.generate_json_from_video_url(
                video_url=video_url,
                prompt=prompt,
                schema=ReferenceBlueprint,
                model=self.settings.gemini_reference_model,
            )

        raise RuntimeError("Reference video requires a local file path or source URL")

    async def analyse_candidate_video(
        self,
        topic: str,
        reference_blueprint: ReferenceBlueprint,
        memory_context: dict[str, Any],
        prompt: str,
        candidate_id: str,
        project_id: str,
        video_path: str | None = None,
        video_url: str | None = None,
    ) -> CandidateVideo:
        preference_guidance = format_video_preferences_for_analysis(memory_context)
        full_prompt = (
            f"{prompt}\n\nTopic: {topic}\n"
            f"Reference blueprint summary: ranking_count={reference_blueprint.ranking_count}, "
            f"hook_style={reference_blueprint.hook_style}, "
            f"rank_reveal={reference_blueprint.rank_reveal_style}, "
            f"duration_sec={reference_blueprint.duration_sec}, "
            f"average_item_duration_sec={reference_blueprint.average_item_duration_sec}, "
            f"aspect_ratio={reference_blueprint.aspect_ratio}\n\n"
            f"Learned video preferences:\n{preference_guidance}\n\n"
            f"Set candidate_id={candidate_id}, project_id={project_id} in output."
        )

        if video_path:
            uploaded = await self.upload_video(video_path)
            active = await self.wait_until_active(uploaded)
            return await self.generate_json_from_video(
                active_file=active,
                prompt=full_prompt,
                schema=CandidateVideo,
                model=self.settings.gemini_candidate_model,
            )

        if video_url:
            return await self.generate_json_from_video_url(
                video_url=video_url,
                prompt=full_prompt,
                schema=CandidateVideo,
                model=self.settings.gemini_candidate_model,
            )

        raise RuntimeError("Candidate video requires a local file path or source URL")

    async def generate_json_from_video(
        self,
        active_file: dict[str, Any],
        prompt: str,
        schema: Type[T],
        model: str,
    ) -> T:
        response_text = await asyncio.to_thread(
            self._generate_content_sync,
            active_file,
            prompt,
            schema,
            model,
        )
        try:
            return schema.model_validate_json(response_text)
        except ValidationError:
            repair_prompt = (
                f"Fix the JSON to strictly match the schema. Previous invalid output:\n{response_text}"
            )
            repaired = await asyncio.to_thread(
                self._generate_content_sync,
                active_file,
                repair_prompt,
                schema,
                model,
            )
            return schema.model_validate_json(repaired)

    async def generate_json_from_video_url(
        self,
        video_url: str,
        prompt: str,
        schema: Type[T],
        model: str,
    ) -> T:
        response_text = await asyncio.to_thread(
            self._generate_content_from_url_sync,
            video_url,
            prompt,
            schema,
            model,
        )
        try:
            return schema.model_validate_json(response_text)
        except ValidationError:
            repair_prompt = (
                f"Fix the JSON to strictly match the schema. Previous invalid output:\n{response_text}"
            )
            repaired = await asyncio.to_thread(
                self._generate_content_from_url_sync,
                video_url,
                repair_prompt,
                schema,
                model,
            )
            return schema.model_validate_json(repaired)

    def _generate_content_from_url_sync(
        self,
        video_url: str,
        prompt: str,
        schema: Type[T],
        model: str,
    ) -> str:
        if not is_single_youtube_video_url(video_url):
            raise ValueError(
                "Gemini video analysis requires a single YouTube video URL "
                "(watch, shorts, or youtu.be). Playlists and channel pages are not supported."
            )

        response = self.client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_uri(file_uri=video_url, mime_type="video/mp4"),
                types.Part.from_text(text=prompt),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned empty response")
        return response.text

    def _generate_content_sync(
        self,
        active_file: dict[str, Any],
        prompt: str,
        schema: Type[T],
        model: str,
    ) -> str:
        response = self.client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_uri(file_uri=active_file["uri"], mime_type=active_file["mime_type"]),
                types.Part.from_text(text=prompt),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned empty response")
        return response.text

    async def generate_json(self, prompt: str, schema: Type[T], model: str | None = None) -> T:
        model_name = model or self.settings.gemini_candidate_model
        response_text = await asyncio.to_thread(
            self._generate_text_json_sync,
            prompt,
            schema,
            model_name,
        )
        try:
            return schema.model_validate_json(response_text)
        except ValidationError:
            repair_prompt = f"Return valid JSON only matching schema. Invalid:\n{response_text}"
            repaired = await asyncio.to_thread(
                self._generate_text_json_sync,
                repair_prompt,
                schema,
                model_name,
            )
            return schema.model_validate_json(repaired)

    def _generate_text_json_sync(self, prompt: str, schema: Type[T], model: str) -> str:
        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned empty response")
        return response.text
