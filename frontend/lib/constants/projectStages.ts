export const PROJECT_STAGE_LABELS: Record<string, string> = {
  created: "Created",
  reference_uploaded: "Reference Uploaded",
  reference_analysed: "Reference Analysed",
  topic_set: "Topic Set",
  topic_researched: "Topic Researched",
  platform_urls_discovered: "URLs Discovered",
  concepts_discovered: "Candidates Discovered",
  candidates_analysed: "Candidates Analysed",
  candidate_review_initialized: "Candidate Review",
  awaiting_candidate_approval: "Awaiting Approval",
  candidates_approved: "Candidates Approved",
  candidate_review_complete: "Review Complete",
  moe_fuse: "Edit Planning",
  edit_plan_ready: "Edit Plan Ready",
  edit_plan_approved: "Edit Plan Approved",
  rendered: "Rendered",
  analyse_reference: "Reference Analysis",
  research_topic: "Topic Research",
  discover_candidates: "Discovering Candidates",
  select_ranking: "Selecting Ranking",
  create_edit_plan: "Edit Plan",
  render: "Rendering",
  compare: "Comparison",
  regenerate: "Regenerating",
  feedback: "Feedback",
};

export function getProjectStageLabel(stage: string): string {
  return PROJECT_STAGE_LABELS[stage] ?? stage.replace(/_/g, " ");
}
