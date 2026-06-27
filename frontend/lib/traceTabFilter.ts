export type ProjectWorkflowTab =
  | "reference"
  | "blueprint"
  | "candidates"
  | "studio"
  | "review"
  | "comparison";

type TraceLike = {
  agent_id: string;
  metadata?: Record<string, unknown>;
};

type DownloadEventLike = {
  stage: string;
  agent_id?: string;
};

type AgentMessageLike = {
  from_agent_id: string;
};

const TAB_AGENT_IDS: Record<ProjectWorkflowTab, readonly string[]> = {
  reference: [
    "reference_video_probe",
    "reference_structure_analysis",
    "reference_audio_analysis",
    "reference_blueprint_memory",
  ],
  blueprint: [
    "reference_video_probe",
    "reference_structure_analysis",
    "reference_audio_analysis",
    "reference_blueprint_memory",
    "topic_agent",
    "mubit_memory",
    "tavily_research",
  ],
  candidates: [
    "candidate_discovery",
    "platform_video_search",
    "platform_video_download",
    "candidate_visual_analysis",
    "candidate_segment_analysis",
    "candidate_preview",
  ],
  studio: [
    "moe_edit_swarm",
    "fusion_agent",
    "slng_audio",
    "critic_agent",
    "story_expert",
    "mubit_memory",
    "render_swarm",
    "rank_clip_render",
    "video_stitch",
    "hook_overlay",
    "audio_mix",
  ],
  review: [
    "render_swarm",
    "rank_clip_render",
    "video_stitch",
    "hook_overlay",
    "audio_mix",
    "mubit_memory",
  ],
  comparison: ["comparison_agent"],
};

const CANDIDATE_DOWNLOAD_STAGES = new Set([
  "search_started",
  "url_selected",
  "download_started",
  "download_success",
  "download_failed",
  "skipped",
]);

function traceMatchesTab(trace: TraceLike, tab: ProjectWorkflowTab): boolean {
  const allowedAgentIds = TAB_AGENT_IDS[tab];
  if (allowedAgentIds.includes(trace.agent_id)) {
    return true;
  }
  const parentAgentId = trace.metadata?.parent_agent_id;
  return typeof parentAgentId === "string" && allowedAgentIds.includes(parentAgentId);
}

export function filterTracesForTab<T extends TraceLike>(traces: T[], tab: ProjectWorkflowTab): T[] {
  return traces.filter((trace) => traceMatchesTab(trace, tab));
}

export function filterDownloadEventsForTab<T extends DownloadEventLike>(
  events: T[],
  tab: ProjectWorkflowTab,
): T[] {
  if (tab === "candidates") {
    return events.filter((event) => CANDIDATE_DOWNLOAD_STAGES.has(event.stage));
  }
  return [];
}

export function filterAgentMessagesForTab<T extends AgentMessageLike>(
  messages: T[],
  tab: ProjectWorkflowTab,
): T[] {
  if (tab === "studio") {
    return messages;
  }
  return [];
}
