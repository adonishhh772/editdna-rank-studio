from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.services.audio_analysis_service import analyse_video_audio_style


class ReferenceAudioAnalysisAgent(BaseAgent):
    agent_id = "reference_audio_analysis"
    agent_name = "Audio Style Analysis"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.reference_blueprint:
            trace = self.active_trace(blackboard)
            trace.status = "complete"
            trace.output_summary = "Skipped — structure analysis required first"
            trace.visible_reasoning = "Waiting for structure blueprint before audio pass."
            return blackboard

        trace = self.active_trace(blackboard)
        trace.input_summary = "Analysing music, voiceover, and sound design"
        trace.visible_reasoning = "Detecting audio mood, energy, and overlay style from the reference."

        try:
            audio_result = await analyse_video_audio_style(
                project_id=blackboard.project_id,
                video_path=blackboard.reference_video_path,
                video_url=blackboard.reference_video_url,
                subdir="reference",
            )
        except Exception as exc:
            trace.output_summary = "Audio analysis unavailable"
            trace.visible_reasoning = f"Audio pass skipped: {exc}"
            return blackboard

        if not audio_result:
            trace.output_summary = "No audio track detected"
            return blackboard

        blackboard.reference_blueprint.audio_style = {
            **blackboard.reference_blueprint.audio_style,
            **audio_result.audio_style,
        }
        if audio_result.local_file_path:
            blackboard.reference_video_path = audio_result.local_file_path

        mood = audio_result.audio_style.get("mood") or audio_result.audio_style.get("energy")
        mean_volume_db = audio_result.audio_style.get("mean_volume_db")
        loudness_hint = (
            f", mean {mean_volume_db:.1f} dB"
            if isinstance(mean_volume_db, (int, float))
            else ""
        )
        trace.output_summary = f"Audio style captured{f' — {mood}{loudness_hint}' if mood or loudness_hint else ''}"
        self.log_tool_call(
            blackboard,
            "slng_audio_analysis",
            {"audio_style_keys": list(audio_result.audio_style.keys())},
        )
        return blackboard
