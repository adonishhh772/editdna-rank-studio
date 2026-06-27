from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from app.schemas import (
    AgentMessage,
    AgentTrace,
    CandidateReviewSlot,
    ComparisonReport,
    DownloadEvent,
    EditPlan,
    ExpertProposal,
    FeedbackEvent,
    HarnessGoalResult,
    MoEFusionResult,
    MoERoutingWeights,
    ReferenceBlueprint,
    TopicResearch,
    CandidateVideo,
)


class ProjectBlackboard(BaseModel):
    project_id: str
    run_id: str
    user_id: str
    title: str = "Untitled Ranking Project"
    stage: str = "created"
    waiting_for_human: bool = False
    human_gate_type: Optional[str] = None

    reference_video_path: Optional[str] = None
    reference_video_url: Optional[str] = None
    reference_blueprint: Optional[ReferenceBlueprint] = None

    topic: Optional[str] = None
    target_platform: str = "generic"

    memory_context: Dict[str, Any] = Field(default_factory=dict)
    topic_research: Optional[TopicResearch] = None

    candidate_pool: List[CandidateVideo] = Field(default_factory=list)
    candidate_review_queue: List[CandidateReviewSlot] = Field(default_factory=list)
    review_active: bool = False
    selected_candidates: List[CandidateVideo] = Field(default_factory=list)
    approved_candidates: List[CandidateVideo] = Field(default_factory=list)
    rejected_candidates: List[CandidateVideo] = Field(default_factory=list)

    edit_plan: Optional[EditPlan] = None
    output_video_path: Optional[str] = None
    current_version: int = 1

    feedback_events: List[FeedbackEvent] = Field(default_factory=list)
    comparison_report: Optional[ComparisonReport] = None
    memory_updates: List[Dict[str, Any]] = Field(default_factory=list)
    download_events: List[DownloadEvent] = Field(default_factory=list)

    traces: List[AgentTrace] = Field(default_factory=list)

    agent_messages: List[AgentMessage] = Field(default_factory=list)
    expert_proposals: List[ExpertProposal] = Field(default_factory=list)
    moe_routing: Optional[MoERoutingWeights] = None
    moe_fusion: Optional[MoEFusionResult] = None

    harness_revision_count: int = 0
    harness_goals_met: bool = True
    harness_goal_results: List[HarnessGoalResult] = Field(default_factory=list)
