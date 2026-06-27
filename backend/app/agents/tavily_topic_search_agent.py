from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.integrations.tavily_client import TavilyResearchClient


class TavilyTopicSearchAgent(BaseAgent):
    agent_id = "tavily_topic_search"
    agent_name = "Tavily Topic Search"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.topic:
            raise RuntimeError("Topic is required")

        ranking_count = (
            blackboard.reference_blueprint.ranking_count
            if blackboard.reference_blueprint
            else 5
        )
        client = TavilyResearchClient()
        search_data = await client.search_topic_async(blackboard.topic, ranking_count)

        trace = self.active_trace(blackboard)
        trace.input_summary = f"Topic: {blackboard.topic[:80]}"
        trace.output_summary = f"Collected {len(search_data.get('results', []))} web results"
        trace.visible_reasoning = "Running Tavily web search for concrete ranking concepts."
        trace.metadata["search_data"] = {
            "result_count": len(search_data.get("results", [])),
            "has_answer": bool(search_data.get("answer")),
        }
        blackboard.memory_context["tavily_search_data"] = search_data
        return blackboard
