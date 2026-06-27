from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional


class AgentMessage(BaseModel):
    message_id: str
    project_id: str
    run_id: str
    round_id: str
    from_agent_id: str
    from_agent_name: str
    to_agent_id: Optional[str] = None
    message_type: Literal[
        "proposal",
        "request",
        "feedback",
        "agreement",
        "conflict",
        "routing",
    ]
    domain: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class ExpertProposal(BaseModel):
    proposal_id: str
    agent_id: str
    agent_name: str
    domain: str
    round_id: str
    confidence: float
    hook_text: Optional[str] = None
    outro_text: Optional[str] = None
    clip_adjustments: List[Dict[str, Any]] = Field(default_factory=list)
    caption_updates: List[Dict[str, Any]] = Field(default_factory=list)
    motion_updates: List[Dict[str, Any]] = Field(default_factory=list)
    transition_updates: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning: str = ""
    peer_influence: List[str] = Field(default_factory=list)


class MoERoutingWeights(BaseModel):
    round_id: str
    story: float = 0.25
    cut: float = 0.25
    caption: float = 0.25
    motion: float = 0.25
    reasoning: str = ""


class MoEFusionResult(BaseModel):
    fusion_id: str
    round_id: str
    hook_text: str
    outro_text: str
    clip_adjustments: List[Dict[str, Any]] = Field(default_factory=list)
    caption_updates: List[Dict[str, Any]] = Field(default_factory=list)
    motion_updates: List[Dict[str, Any]] = Field(default_factory=list)
    transition_updates: List[Dict[str, Any]] = Field(default_factory=list)
    routing_weights: MoERoutingWeights
    expert_contributions: Dict[str, float] = Field(default_factory=dict)
    consensus_notes: List[str] = Field(default_factory=list)


class AgentTrace(BaseModel):
    trace_id: str
    project_id: str
    run_id: str
    agent_id: str
    agent_name: str
    status: Literal["pending", "running", "waiting_for_human", "complete", "failed"]
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    visible_reasoning: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DownloadEvent(BaseModel):
    event_id: str
    project_id: str
    run_id: str
    agent_id: str
    agent_name: str
    candidate_id: Optional[str] = None
    concept: str
    stage: Literal[
        "search_started",
        "search_result",
        "url_selected",
        "download_started",
        "download_success",
        "download_failed",
        "skipped",
    ]
    platform: Optional[str] = None
    search_query: Optional[str] = None
    source_url: Optional[str] = None
    local_file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class ReferenceSection(BaseModel):
    name: str
    rank_number: Optional[int] = None
    start_sec: float
    end_sec: float
    purpose: str
    visual_notes: str
    audio_notes: str
    text_notes: str
    motion_notes: str


class ReferenceBlueprint(BaseModel):
    blueprint_id: str
    project_id: str
    video_type: Literal["ranking_video"]
    aspect_ratio: str
    duration_sec: float
    ranking_count: int
    ranking_order: Literal["5_to_1", "1_to_5", "unknown"]
    hook_duration_sec: float
    average_item_duration_sec: float
    outro_duration_sec: float
    section_order: List[ReferenceSection]
    caption_style: Dict[str, Any]
    text_overlay_style: Dict[str, Any]
    transition_style: Dict[str, Any]
    audio_style: Dict[str, Any]
    motion_style: Dict[str, Any]
    pacing_style: Dict[str, Any]
    hook_style: str
    rank_reveal_style: str
    final_rank_drama_level: Literal["low", "medium", "high"]
    confidence: float


class TopicResearch(BaseModel):
    project_id: str
    topic: str
    ranking_count: int
    research_summary: str
    candidate_concepts: List[str]
    source_urls: List[str] = Field(default_factory=list)
    search_results: List[Dict[str, Any]] = Field(default_factory=list)
    reference_video_format: Literal["shorts", "regular", "unknown"] = "unknown"
    reference_video_orientation: Literal["mobile", "landscape", "unknown"] = "unknown"
    youtube_search_mode: Literal["shorts", "regular", "any"] = "any"
    aspect_ratio_hint: str = "unknown"
    target_candidate_duration_sec: float | None = None
    rank_segment_duration_sec: float | None = None
    max_source_duration_sec: float | None = None
    min_source_duration_sec: float | None = None


class CandidateVideo(BaseModel):
    candidate_id: str
    project_id: str
    title: str
    source_type: Literal["user_upload", "sample_asset", "licensed_asset_url", "public_url_reference"]
    source_url: Optional[str] = None
    local_file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    concept: str
    duration_sec: Optional[float] = None
    clip_start_sec: Optional[float] = None
    clip_end_sec: Optional[float] = None
    highlight_reason: Optional[str] = None
    topic_match_score: float
    visual_quality_score: float
    audio_quality_score: float
    motion_energy_score: float
    text_relevance_score: float
    reference_style_fit_score: float
    source_safety_score: float
    overall_score: float
    recommended_rank: Optional[int] = None
    reason: str
    status: Literal["candidate", "selected", "approved", "rejected", "replacement_needed"] = "candidate"


class CandidateReviewSlot(BaseModel):
    slot_rank: int
    concept: str
    status: Literal["pending", "preparing", "awaiting_approval", "approved", "exhausted"] = "pending"
    rejected_urls: List[str] = Field(default_factory=list)
    search_attempts: int = 0
    current_candidate: Optional[CandidateVideo] = None
    approved_candidate: Optional[CandidateVideo] = None
    last_error: Optional[str] = None


class CandidateReviewStatusResponse(BaseModel):
    review_active: bool
    total_slots: int
    approved_count: int
    pending_count: int
    exhausted_count: int
    current_slot_rank: Optional[int] = None
    current_status: Optional[str] = None
    current_candidate: Optional[CandidateVideo] = None
    message: str = ""


class RankedClip(BaseModel):
    rank: int
    candidate_id: str
    title: str
    source_file_path: str
    clip_start_sec: float
    clip_end_sec: float
    label_text: str
    voiceover_text: Optional[str] = None
    caption_text: Optional[str] = None
    reason: str


class EditPlan(BaseModel):
    edit_plan_id: str
    project_id: str
    version: int
    topic: str
    output_aspect_ratio: str
    output_duration_sec: float
    hook_text: str
    outro_text: str
    sections: List[RankedClip]
    captions: List[Dict[str, Any]]
    audio_plan: Dict[str, Any]
    motion_plan: List[Dict[str, Any]]
    transition_plan: List[Dict[str, Any]]
    render_settings: Dict[str, Any]
    reference_blueprint_applied: Dict[str, Any]
    memory_influence: Dict[str, Any]
    needs_human_approval: bool = True


class FeedbackEvent(BaseModel):
    feedback_id: str
    project_id: str
    run_id: str
    user_id: str
    feedback_type: Literal[
        "approve",
        "reject",
        "replace",
        "reorder",
        "text_feedback",
        "voice_feedback",
        "final_approve",
    ]
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    feedback_text: Optional[str] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class MemoryUpdate(BaseModel):
    memory_update_id: str
    project_id: str
    run_id: str
    user_id: str
    short_term_updates: List[Dict[str, Any]] = Field(default_factory=list)
    episodic_updates: List[Dict[str, Any]] = Field(default_factory=list)
    long_term_updates: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float
    summary: str


class HarnessGoalResult(BaseModel):
    goal_id: str
    met: bool
    issue: Optional[str] = None


class ComparisonReport(BaseModel):
    project_id: str
    reference_match_score: float
    user_preference_match_score: float
    pacing_match_score: float
    caption_style_match_score: float
    audio_style_match_score: float
    ranking_structure_match_score: float
    topic_relevance_score: float
    issues: List[str]
    improvements_after_feedback: List[str]
    learned_preferences: List[str]


class ProjectCreateRequest(BaseModel):
    user_id: str = "default-user"
    title: str = "Untitled Ranking Project"


class ReferenceVideoUrlRequest(BaseModel):
    video_url: str


class TopicRequest(BaseModel):
    topic: str
    target_platform: str = "generic"


class CandidateApprovalRequest(BaseModel):
    user_id: str = "default-user"


class CandidateReorderRequest(BaseModel):
    candidate_ids: List[str]
    user_id: str = "default-user"


class TextFeedbackRequest(BaseModel):
    feedback_text: str
    feedback_type: str = "text_feedback"
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    user_id: str = "default-user"


class ProjectSummaryResponse(BaseModel):
    project_id: str
    title: str
    stage: str
    user_id: str
    created_at: str
    updated_at: str


class ApiStatusResponse(BaseModel):
    gemini: bool
    tavily: bool
    slng: bool
    mubit: bool
    missing_keys: List[str]
    allow_demo_fallback: bool
