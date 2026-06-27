export type VideoAnalysisScore = {
  key: string;
  label: string;
  value: number;
  accent?: "blue" | "purple" | "green" | "teal" | "orange" | "pink";
};

export type CandidateVideoInsight = {
  candidateId: string;
  rank: number;
  title: string;
  sourceVideoTitle: string;
  concept: string;
  reason: string;
  highlightReason: string;
  voiceoverText: string;
  clipRange: string;
  analysisSource: string;
  needsImprovement: boolean;
  storyCoherenceScore: number | null;
  scores: VideoAnalysisScore[];
};

export type ReferenceVideoInsight = {
  hookStyle: string;
  rankRevealStyle: string;
  rankingCount: number;
  averageItemDurationSec: number;
  finalRankDramaLevel: string;
  aspectRatio: string;
  durationSec: number;
};

export type EditVideoInsights = {
  reference: ReferenceVideoInsight | null;
  candidates: CandidateVideoInsight[];
};

const SCORE_LABELS: Record<string, { label: string; accent: VideoAnalysisScore["accent"] }> = {
  topic_match: { label: "Topic Match", accent: "blue" },
  visual_quality: { label: "Visual Quality", accent: "purple" },
  audio_quality: { label: "Audio Quality", accent: "green" },
  motion_energy: { label: "Motion Energy", accent: "teal" },
  text_relevance: { label: "Text Relevance", accent: "orange" },
  reference_style_fit: { label: "Style Fit", accent: "pink" },
  story_coherence: { label: "Story Coherence", accent: "green" },
  overall: { label: "Overall", accent: "blue" },
};

function formatClipRange(startSec: unknown, endSec: unknown): string {
  const start = typeof startSec === "number" ? startSec : Number(startSec);
  const end = typeof endSec === "number" ? endSec : Number(endSec);
  if (Number.isFinite(start) && Number.isFinite(end)) {
    return `${start.toFixed(1)}s – ${end.toFixed(1)}s`;
  }
  return "Full clip";
}

function buildScoreEntries(scores: Record<string, unknown> | undefined): VideoAnalysisScore[] {
  if (!scores) {
    return [];
  }

  return Object.entries(SCORE_LABELS)
    .map(([key, meta]) => {
      const rawValue = scores[key];
      const value = typeof rawValue === "number" ? rawValue : Number(rawValue);
      if (!Number.isFinite(value)) {
        return null;
      }
      return {
        key,
        label: meta.label,
        value,
        accent: meta.accent,
      };
    })
    .filter((entry): entry is VideoAnalysisScore => entry !== null);
}

export function buildEditVideoInsightsFromPlan(
  editPlan: Record<string, unknown> | null | undefined,
): EditVideoInsights {
  const rawInsights = (editPlan?.video_insights as Record<string, unknown>) || {};
  const rawReference = rawInsights.reference as Record<string, unknown> | null | undefined;
  const rawCandidates = (rawInsights.candidates as Array<Record<string, unknown>>) || [];

  const reference = rawReference
    ? {
        hookStyle: String(rawReference.hook_style || "unknown"),
        rankRevealStyle: String(rawReference.rank_reveal_style || "unknown"),
        rankingCount: Number(rawReference.ranking_count || 0),
        averageItemDurationSec: Number(rawReference.average_item_duration_sec || 0),
        finalRankDramaLevel: String(rawReference.final_rank_drama_level || "medium"),
        aspectRatio: String(rawReference.aspect_ratio || "unknown"),
        durationSec: Number(rawReference.duration_sec || 0),
      }
    : null;

  const candidates = rawCandidates.map((entry) => ({
    candidateId: String(entry.candidate_id || ""),
    rank: Number(entry.rank || 0),
    title: String(entry.video_moment_title || entry.title || "Untitled clip"),
    sourceVideoTitle: String(entry.source_video_title || entry.title || ""),
    concept: String(entry.concept || ""),
    reason: String(entry.reason || ""),
    highlightReason: String(entry.highlight_reason || ""),
    voiceoverText: String(entry.voiceover_text || ""),
    clipRange: formatClipRange(entry.clip_start_sec, entry.clip_end_sec),
    analysisSource: String(entry.analysis_source || "gemini"),
    needsImprovement: Boolean(entry.needs_improvement),
    storyCoherenceScore:
      typeof entry.story_coherence_score === "number" ? entry.story_coherence_score : null,
    scores: buildScoreEntries(entry.scores as Record<string, unknown> | undefined),
  }));

  return { reference, candidates };
}

export function buildEditVideoInsightsFromSections(
  editPlan: Record<string, unknown> | null | undefined,
): EditVideoInsights {
  const fromPlan = buildEditVideoInsightsFromPlan(editPlan);
  if (fromPlan.candidates.length > 0 || fromPlan.reference) {
    return fromPlan;
  }

  const sections = (editPlan?.sections as Array<Record<string, unknown>>) || [];
  const candidates = sections.map((section) => ({
    candidateId: String(section.candidate_id || ""),
    rank: Number(section.rank || 0),
    title: String(section.video_moment_title || section.title || section.label_text || "Untitled clip"),
    sourceVideoTitle: String(section.source_video_title || section.title || ""),
    concept: String(section.label_text || ""),
    reason: String(section.reason || ""),
    highlightReason: String(section.highlight_reason || ""),
    voiceoverText: String(section.voiceover_text || ""),
    clipRange: formatClipRange(section.clip_start_sec, section.clip_end_sec),
    analysisSource: "gemini",
    needsImprovement: Boolean(section.needs_improvement),
    storyCoherenceScore:
      typeof section.story_coherence_score === "number" ? section.story_coherence_score : null,
    scores: buildScoreEntries(section.analysis_scores as Record<string, unknown> | undefined),
  }));

  return { reference: null, candidates };
}
