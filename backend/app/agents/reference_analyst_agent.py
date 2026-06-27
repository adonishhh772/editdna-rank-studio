from app.agents.base import BaseAgent
from app.agents.mubit_memory_agent import ReferenceBlueprintMemoryAgent
from app.agents.reference_audio_analysis_agent import ReferenceAudioAnalysisAgent
from app.agents.reference_format_detection_agent import ReferenceFormatDetectionAgent
from app.agents.reference_structure_agent import ReferenceStructureAgent
from app.agents.reference_video_probe_agent import ReferenceVideoProbeAgent
from app.blackboard import ProjectBlackboard
from app.services.video_analysis_store import save_reference_video_analysis
from app.services.video_constraint_service import ReferenceVideoConstraints, constraints_summary


class ReferenceAnalystAgent(BaseAgent):
    agent_id = "reference_analyst"
    agent_name = "Reference Analyst"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        has_local = bool(blackboard.reference_video_path)
        has_url = bool(blackboard.reference_video_url)
        if not has_local and not has_url:
            raise RuntimeError("Reference video path or URL is required")

        parent_trace = self.active_trace(blackboard)
        parent_agent_id = self.agent_id

        probe_agent = ReferenceVideoProbeAgent()
        structure_agent = ReferenceStructureAgent()
        audio_agent = ReferenceAudioAnalysisAgent()
        memory_agent = ReferenceBlueprintMemoryAgent()

        sub_agents = [ReferenceVideoProbeAgent.agent_id]

        blackboard = await probe_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )

        if blackboard.reference_video_url:
            format_agent = ReferenceFormatDetectionAgent()
            blackboard = await format_agent.execute(
                blackboard,
                parent_agent_id=parent_agent_id,
                swarm=True,
            )
            sub_agents.append(ReferenceFormatDetectionAgent.agent_id)

        blackboard = await structure_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )
        sub_agents.append(ReferenceStructureAgent.agent_id)

        blackboard = await audio_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )
        sub_agents.append(ReferenceAudioAnalysisAgent.agent_id)

        if blackboard.reference_blueprint:
            constraints = ReferenceVideoConstraints.from_blueprint(blackboard.reference_blueprint)
            blackboard.memory_context["reference_video_constraints"] = constraints_summary(constraints)
            save_reference_video_analysis(blackboard)

        blackboard.stage = "reference_analysed"
        blackboard = await memory_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )
        sub_agents.append(ReferenceBlueprintMemoryAgent.agent_id)

        blueprint = blackboard.reference_blueprint
        parent_trace.input_summary = "Reference analysis swarm"
        if blueprint:
            parent_trace.output_summary = (
                f"Blueprint ready: {blueprint.ranking_count} ranks, hook {blueprint.hook_duration_sec}s"
            )
        parent_trace.visible_reasoning = (
            "Swarm probed format, extracted structure/pacing, analysed audio, and saved to memory."
        )
        parent_trace.metadata["sub_agents"] = sub_agents
        parent_trace.metadata["swarm"] = True
        return blackboard
