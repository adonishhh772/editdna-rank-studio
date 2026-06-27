import logging

from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.constants.feedback import (
    FEEDBACK_SENTIMENT_NEGATIVE,
    FEEDBACK_SENTIMENT_POSITIVE,
)
from app.db import new_id, save_blackboard
from app.integrations.mubit_client import MubitMemoryClient
from app.schemas import MemoryUpdate
from app.services.blueprint_memory import build_reference_blueprint_memory_content
from app.services.feedback_learning_service import (
    build_memory_scope_updates,
    classify_feedback_sentiment,
    feedback_memory_summary,
)

logger = logging.getLogger(__name__)


class MubitMemoryAgent(BaseAgent):
    agent_id = "mubit_memory"
    agent_name = "Mubit Memory Agent"

    async def recall_context(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        client = MubitMemoryClient(run_id=blackboard.run_id)
        context = await client.recall_context(
            user_id=blackboard.user_id,
            project_id=blackboard.project_id,
            topic=blackboard.topic or "",
            video_type="ranking_video",
        )
        blackboard.memory_context = context
        blackboard.traces[-1].output_summary = "Recalled memory context from Mubit"
        return blackboard

    async def write_feedback_memory(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        recent_feedback = blackboard.feedback_events[-5:]
        short_term: list[dict] = []
        episodic: list[dict] = []
        long_term: list[dict] = []

        for feedback in recent_feedback:
            sentiment = classify_feedback_sentiment(feedback.feedback_text, feedback.feedback_type)
            scoped_short, scoped_episodic, scoped_long = build_memory_scope_updates(feedback, sentiment)
            short_term.extend(scoped_short)
            episodic.extend(scoped_episodic)
            long_term.extend(scoped_long)

        mubit_synced = True
        try:
            client = MubitMemoryClient(run_id=blackboard.run_id)
            for feedback in recent_feedback:
                content = feedback.feedback_text or feedback.feedback_type
                sentiment = classify_feedback_sentiment(feedback.feedback_text, feedback.feedback_type)
                metadata = {
                    "memory_scope": "short_term",
                    "feedback_type": feedback.feedback_type,
                    "sentiment": sentiment,
                    "topic": blackboard.topic or "",
                }
                await client.remember_short_term(
                    user_id=blackboard.user_id,
                    project_id=blackboard.project_id,
                    run_id=blackboard.run_id,
                    agent_id=self.agent_id,
                    content=content,
                    metadata=metadata,
                )
                if sentiment in {FEEDBACK_SENTIMENT_POSITIVE, FEEDBACK_SENTIMENT_NEGATIVE}:
                    await client.remember_episodic(
                        user_id=blackboard.user_id,
                        project_id=blackboard.project_id,
                        run_id=blackboard.run_id,
                        agent_id=self.agent_id,
                        content=f"In project {blackboard.project_id}: {content}",
                        metadata={**metadata, "memory_scope": "episodic"},
                    )
                if sentiment == FEEDBACK_SENTIMENT_POSITIVE or (
                    feedback.feedback_text
                    and sentiment == FEEDBACK_SENTIMENT_NEGATIVE
                    and any(
                        marker in feedback.feedback_text.lower()
                        for marker in ("prefer", "always", "never", "dislike", "like")
                    )
                ):
                    await client.remember_long_term(
                        user_id=blackboard.user_id,
                        project_id=blackboard.project_id,
                        run_id=blackboard.run_id,
                        agent_id=self.agent_id,
                        content=feedback.feedback_text or content,
                        metadata={**metadata, "memory_scope": "long_term"},
                    )
        except Exception as error:
            mubit_synced = False
            logger.warning(
                "Failed to persist feedback memory to Mubit for project %s: %s",
                blackboard.project_id,
                error,
            )

        latest_sentiment = (
            classify_feedback_sentiment(
                recent_feedback[-1].feedback_text,
                recent_feedback[-1].feedback_type,
            )
            if recent_feedback
            else "neutral"
        )
        update = MemoryUpdate(
            memory_update_id=new_id("mem"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            user_id=blackboard.user_id,
            short_term_updates=short_term,
            episodic_updates=episodic,
            long_term_updates=long_term,
            confidence=0.85 if short_term and mubit_synced else 0.5,
            summary=feedback_memory_summary(
                short_term_count=len(short_term),
                episodic_count=len(episodic),
                long_term_count=len(long_term),
                sentiment=latest_sentiment,
                mubit_synced=mubit_synced,
            ),
        )
        blackboard.memory_updates.append(update.model_dump())
        blackboard.traces[-1].output_summary = update.summary
        return blackboard

    async def write_reference_blueprint_memory(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        blueprint = blackboard.reference_blueprint
        if blueprint is None:
            return blackboard

        content = build_reference_blueprint_memory_content(blueprint)
        metadata = {
            "source": "reference_blueprint",
            "blueprint_id": blueprint.blueprint_id,
            "topic": blackboard.topic or "",
        }

        episodic_updates: list[dict] = [{"content": content}]
        style_preference = (
            f"User prefers ranking videos with {blueprint.hook_style} hooks, "
            f"{blueprint.rank_reveal_style} reveals, and {blueprint.final_rank_drama_level} drama."
        )
        long_term_updates: list[dict] = [{"content": style_preference}]

        try:
            client = MubitMemoryClient(run_id=blackboard.run_id)
            await client.remember_episodic(
                user_id=blackboard.user_id,
                project_id=blackboard.project_id,
                run_id=blackboard.run_id,
                agent_id=self.agent_id,
                content=content,
                metadata={
                    **metadata,
                    "memory_scope": MubitMemoryClient.MEMORY_SCOPE_EPISODIC,
                },
            )
            await client.remember_long_term(
                user_id=blackboard.user_id,
                project_id=blackboard.project_id,
                run_id=blackboard.run_id,
                agent_id=self.agent_id,
                content=style_preference,
                metadata={
                    **metadata,
                    "memory_scope": MubitMemoryClient.MEMORY_SCOPE_LONG,
                },
            )
        except Exception as error:
            logger.warning(
                "Failed to persist reference blueprint memory to Mubit for project %s: %s",
                blackboard.project_id,
                error,
            )

        update = MemoryUpdate(
            memory_update_id=new_id("mem"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            user_id=blackboard.user_id,
            episodic_updates=episodic_updates,
            long_term_updates=long_term_updates,
            confidence=blueprint.confidence,
            summary=f"Stored reference blueprint style memory ({blueprint.ranking_count} ranks)",
        )
        blackboard.memory_updates.append(update.model_dump())
        blackboard.memory_context["reference_blueprint_memory"] = {
            "summary": update.summary,
            "hook_style": blueprint.hook_style,
            "rank_reveal_style": blueprint.rank_reveal_style,
            "ranking_count": blueprint.ranking_count,
            "hook_duration_sec": blueprint.hook_duration_sec,
            "final_rank_drama_level": blueprint.final_rank_drama_level,
        }
        save_blackboard(blackboard)
        return blackboard

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        return await self.recall_context(blackboard)


class ReferenceBlueprintMemoryAgent(BaseAgent):
    agent_id = "reference_blueprint_memory"
    agent_name = "Reference Memory Writer"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        trace = self.active_trace(blackboard)
        trace.input_summary = "Persisting reference editing DNA to project memory"

        memory_agent = MubitMemoryAgent()
        blackboard = await memory_agent.write_reference_blueprint_memory(blackboard)

        latest_update = blackboard.memory_updates[-1] if blackboard.memory_updates else None
        if latest_update:
            episodic_count = len(latest_update.get("episodic_updates") or [])
            long_term_count = len(latest_update.get("long_term_updates") or [])
            trace.output_summary = str(latest_update.get("summary", "Reference memory saved"))
            trace.visible_reasoning = (
                f"Saved reference blueprint to episodic and long-term memory "
                f"({episodic_count} episodic, {long_term_count} long-term)."
            )
            self.log_tool_call(
                blackboard,
                "reference_blueprint_memory",
                {
                    "episodic_count": episodic_count,
                    "long_term_count": long_term_count,
                    "ranking_count": blackboard.reference_blueprint.ranking_count
                    if blackboard.reference_blueprint
                    else 0,
                },
            )
            return blackboard

        trace.output_summary = "Skipped reference memory — no blueprint extracted"
        trace.visible_reasoning = "Reference blueprint was not available to persist."
        return blackboard
