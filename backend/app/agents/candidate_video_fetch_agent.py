from app.agents.base import BaseAgent
from app.agents.platform_video_download_agent import PlatformVideoDownloadAgent
from app.agents.platform_video_search_agent import PlatformVideoSearchAgent
from app.blackboard import ProjectBlackboard


class CandidateVideoFetchAgent(BaseAgent):
    """Coordinates platform search + download as explicit swarm sub-stages with full tracing."""

    agent_id = "candidate_video_fetch"
    agent_name = "Candidate Video Fetch Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        search_agent = PlatformVideoSearchAgent()
        download_agent = PlatformVideoDownloadAgent(target="pool")

        blackboard = await search_agent.execute(blackboard)
        blackboard = await download_agent.execute(blackboard)

        parent_trace = self.active_trace(blackboard)
        parent_trace.input_summary = "Orchestrated platform video search and download sub-agents"
        parent_trace.output_summary = (
            f"{len(blackboard.download_events)} download events recorded across search + download agents"
        )
        parent_trace.visible_reasoning = (
            "Delegated to PlatformVideoSearchAgent then PlatformVideoDownloadAgent. "
            "See child agent traces and download_events on the blackboard."
        )
        parent_trace.metadata["sub_agents"] = [
            PlatformVideoSearchAgent.agent_id,
            PlatformVideoDownloadAgent.agent_id,
        ]
        return blackboard
