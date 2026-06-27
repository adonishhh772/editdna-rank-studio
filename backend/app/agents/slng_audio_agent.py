from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.integrations.slng_client import SLNGAudioClient


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
                path = await client.generate_voiceover(text, output_path)
                blackboard.edit_plan.audio_plan["voiceover_path"] = path
                blackboard.traces[-1].output_summary = "Generated voiceover via SLNG TTS"
            except Exception as exc:
                blackboard.traces[-1].metadata["slng_error"] = str(exc)
        return blackboard
