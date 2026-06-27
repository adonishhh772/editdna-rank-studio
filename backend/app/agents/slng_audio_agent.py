from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.constants.audio_style import AUDIO_PLAN_VOICEOVER_GAIN_DB
from app.integrations.slng_client import SLNGAudioClient
from app.services.audio_utils import apply_audio_gain_db


class SLNGAudioAgent(BaseAgent):
    agent_id = "slng_audio"
    agent_name = "SLNG Audio Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if blackboard.edit_plan and blackboard.edit_plan.sections:
            try:
                client = SLNGAudioClient()
                ordered_sections = sorted(
                    blackboard.edit_plan.sections,
                    key=lambda section: section.rank,
                )
                voiceover_lines = [
                    section.voiceover_text or section.label_text
                    for section in ordered_sections
                    if section.voiceover_text or section.label_text
                ]
                text = ". ".join(voiceover_lines)
                output_path = f"outputs/{blackboard.project_id}/voiceover_v{blackboard.current_version}.wav"
                raw_path = await client.generate_voiceover(text, output_path)

                audio_plan = blackboard.edit_plan.audio_plan
                voiceover_gain_db = float(audio_plan.get(AUDIO_PLAN_VOICEOVER_GAIN_DB) or 0.0)
                boosted_path = f"outputs/{blackboard.project_id}/voiceover_v{blackboard.current_version}_boosted.wav"
                final_path = await apply_audio_gain_db(raw_path, boosted_path, voiceover_gain_db)

                audio_plan["voiceover_path"] = final_path
                blackboard.traces[-1].output_summary = (
                    f"Generated voiceover via SLNG TTS"
                    f"{f' (+{voiceover_gain_db:.0f} dB reference boost)' if voiceover_gain_db > 0 else ''}"
                )
            except Exception as exc:
                blackboard.traces[-1].metadata["slng_error"] = str(exc)
        return blackboard
