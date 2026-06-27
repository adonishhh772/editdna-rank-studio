from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.integrations.tavily_client import TavilyResearchClient


class TavilyDeepResearchAgent(BaseAgent):
    agent_id = "tavily_deep_research"
    agent_name = "Tavily Deep Research"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.topic:
            raise RuntimeError("Topic is required")

        ranking_count = (
            blackboard.reference_blueprint.ranking_count
            if blackboard.reference_blueprint
            else 5
        )
        client = TavilyResearchClient()
        research_data = await client.research_topic_focused_async(blackboard.topic, ranking_count)

        trace = self.active_trace(blackboard)
        trace.input_summary = f"Deep research for: {blackboard.topic[:80]}"
        if research_data:
            source_count = len(research_data.get("sources", []))
            trace.output_summary = f"Deep research completed with {source_count} sources"
            trace.visible_reasoning = "Polling Tavily research API for ranked concept list."
        else:
            trace.output_summary = "Deep research unavailable — using web search only"
            trace.visible_reasoning = "Tavily research task failed or timed out; falling back to search results."
        trace.metadata["research_data"] = {
            "available": research_data is not None,
            "source_count": len(research_data.get("sources", [])) if research_data else 0,
        }
        blackboard.memory_context["tavily_research_data"] = research_data
        return blackboard
