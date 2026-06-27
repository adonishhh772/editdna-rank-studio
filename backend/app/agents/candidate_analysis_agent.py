import asyncio
from pathlib import Path

from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.constants.video_sources import is_single_youtube_video_url
from app.integrations.gemini_client import GeminiVideoClient
from app.services.audio_analysis_service import analyse_video_audio_style
from app.services.segment_selection_service import apply_reference_segment_to_candidate
from app.services.video_utils import generate_thumbnail, get_video_duration


class CandidateAnalysisAgent(BaseAgent):
    agent_id = "candidate_analysis"
    agent_name = "Candidate Analysis Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.reference_blueprint:
            raise RuntimeError("Reference blueprint is required")

        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "candidate_analysis.md"
        prompt = prompt_path.read_text(encoding="utf-8")
        gemini = GeminiVideoClient()

        analyzable = [
            candidate
            for candidate in blackboard.candidate_pool
            if (candidate.local_file_path and Path(candidate.local_file_path).exists())
            or (candidate.source_url and is_single_youtube_video_url(candidate.source_url))
        ]

        async def analyze_one(candidate):
            has_local = candidate.local_file_path and Path(candidate.local_file_path).exists()
            analyzed = await gemini.analyse_candidate_video(
                topic=blackboard.topic or "",
                reference_blueprint=blackboard.reference_blueprint,
                memory_context=blackboard.memory_context,
                prompt=prompt,
                candidate_id=candidate.candidate_id,
                project_id=blackboard.project_id,
                video_path=candidate.local_file_path if has_local else None,
                video_url=candidate.source_url if not has_local else None,
            )
            analyzed.candidate_id = candidate.candidate_id
            analyzed.project_id = blackboard.project_id
            analyzed.local_file_path = candidate.local_file_path
            analyzed.source_url = candidate.source_url
            analyzed.source_type = candidate.source_type

            if has_local and candidate.local_file_path:
                analyzed.duration_sec = await get_video_duration(candidate.local_file_path)
                if blackboard.reference_blueprint:
                    analyzed = apply_reference_segment_to_candidate(analyzed, blackboard.reference_blueprint)
                thumb_at_sec = analyzed.clip_start_sec or 1.0
                thumb_path = str(Path(candidate.local_file_path).with_suffix(".thumb.jpg"))
                try:
                    await generate_thumbnail(candidate.local_file_path, thumb_path, at_sec=thumb_at_sec)
                    analyzed.thumbnail_path = thumb_path
                except Exception:
                    pass

            try:
                audio_result = await analyse_video_audio_style(
                    project_id=blackboard.project_id,
                    video_path=candidate.local_file_path if has_local else None,
                    video_url=None,
                    subdir="candidates",
                )
                if audio_result:
                    if audio_result.local_file_path:
                        analyzed.local_file_path = audio_result.local_file_path
                        if not analyzed.duration_sec:
                            analyzed.duration_sec = await get_video_duration(audio_result.local_file_path)
                        thumb_path = str(Path(audio_result.local_file_path).with_suffix(".thumb.jpg"))
                        try:
                            await generate_thumbnail(audio_result.local_file_path, thumb_path)
                            analyzed.thumbnail_path = thumb_path
                        except Exception:
                            pass
                    if audio_result.audio_style.get("has_speech"):
                        analyzed.audio_quality_score = min(analyzed.audio_quality_score + 0.1, 1.0)
            except Exception:
                pass
            return analyzed

        analyzed_count = 0
        if analyzable:
            gather_results = await asyncio.gather(
                *[analyze_one(item) for item in analyzable],
                return_exceptions=True,
            )
            results = []
            failed_count = 0
            for candidate, outcome in zip(analyzable, gather_results):
                if isinstance(outcome, Exception):
                    failed_count += 1
                    candidate.reason = f"Gemini analysis failed: {outcome}"
                    results.append(candidate)
                    continue
                results.append(outcome)

            analyzed_count = len(analyzable) - failed_count
            analyzed_ids = {item.candidate_id for item in results}
            remaining = [item for item in blackboard.candidate_pool if item.candidate_id not in analyzed_ids]
            blackboard.candidate_pool = list(results) + remaining
            if failed_count:
                blackboard.traces[-1].visible_reasoning = (
                    f"Analysed {analyzed_count}/{len(analyzable)} videos; "
                    f"{failed_count} failed (often playlist or unsupported URLs)."
                )

        blackboard.stage = "candidates_analysed"
        blackboard.traces[-1].output_summary = (
            f"Analysed {analyzed_count}/{len(analyzable)} candidate videos"
            if analyzable
            else "No analyzable candidate videos"
        )
        return blackboard
