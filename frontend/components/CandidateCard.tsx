"use client";

import { ArrowDown, ArrowUp, Check, Replace, X } from "lucide-react";
import { resolveUploadMediaUrl } from "@/lib/mediaUrl";

type Candidate = {
  candidate_id: string;
  title: string;
  concept: string;
  reason: string;
  highlight_reason?: string;
  video_moment_title?: string;
  story_coherence_score?: number;
  recommended_rank?: number;
  topic_match_score: number;
  reference_style_fit_score: number;
  overall_score: number;
  local_file_path?: string;
  source_url?: string;
};

type CandidateCardProps = {
  candidate: Candidate;
  isBusy?: boolean;
  isReadOnly?: boolean;
  variant?: "default" | "rejected";
  onApprove: (candidateId: string) => void;
  onReject: (candidateId: string) => void;
  onMoveUp: (candidateId: string) => void;
  onMoveDown: (candidateId: string) => void;
};

export function CandidateCard({
  candidate,
  isBusy = false,
  isReadOnly = false,
  variant = "default",
  onApprove,
  onReject,
  onMoveUp,
  onMoveDown,
}: CandidateCardProps) {
  const previewUrl = resolveUploadMediaUrl(candidate.local_file_path);
  const displayTitle = candidate.title.trim() || candidate.concept;
  const showConceptSubtitle =
    candidate.concept.trim().length > 0 && candidate.concept.trim() !== displayTitle;
  const storyCoherence = candidate.story_coherence_score ?? null;
  const needsStoryImprovement = storyCoherence !== null && storyCoherence < 0.65;

  const isRejectedVariant = variant === "rejected";

  return (
    <div
      className={`glass-card ${isRejectedVariant ? "border-pink-500/30" : ""}`}
      data-testid={`candidate-card-${candidate.candidate_id}`}
    >
      {isRejectedVariant && (
        <p
          className="mb-3 text-xs font-bold uppercase tracking-wider text-pink-400"
          data-testid={`candidate-rejected-badge-${candidate.candidate_id}`}
        >
          Rejected
        </p>
      )}
      {previewUrl && (
        <video
          className="mb-4 w-full rounded-xl border border-white/10"
          controls
          preload="metadata"
          src={previewUrl}
          data-testid={`candidate-preview-${candidate.candidate_id}`}
        />
      )}
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          {candidate.recommended_rank != null && (
            <p className="text-xs uppercase tracking-wider text-neonBlue">
              Rank #{candidate.recommended_rank}
            </p>
          )}
          <h3 className="text-lg font-semibold" data-testid={`candidate-title-${candidate.candidate_id}`}>
            {displayTitle}
          </h3>
          {showConceptSubtitle && (
            <p className="mt-1 text-sm text-slate-400">{candidate.concept}</p>
          )}
        </div>
        <div className="rounded-lg bg-neonPurple/20 px-3 py-1 text-sm font-bold text-neonPurple">
          {(candidate.overall_score * 100).toFixed(0)}
        </div>
      </div>
      <p className="mb-4 text-sm text-slate-300">{candidate.reason}</p>
      {needsStoryImprovement && (
        <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-amber-400" data-testid="candidate-story-warning">
          Story mismatch — voiceover may not match this clip
        </p>
      )}
      {candidate.source_url && !previewUrl && (
        <p className="mb-4 truncate text-xs text-slate-500" title={candidate.source_url}>
          Source: {candidate.source_url}
        </p>
      )}
      <div className="mb-4 grid grid-cols-2 gap-2 text-xs text-slate-400">
        <span>Topic: {(candidate.topic_match_score * 100).toFixed(0)}%</span>
        <span>Style: {(candidate.reference_style_fit_score * 100).toFixed(0)}%</span>
        {storyCoherence !== null && (
          <span>Story: {(storyCoherence * 100).toFixed(0)}%</span>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {!isReadOnly && (
          <>
        <button
          type="button"
          className="glass-button flex items-center gap-1"
          onClick={() => onApprove(candidate.candidate_id)}
          disabled={isBusy}
          data-testid={`approve-candidate-${candidate.candidate_id}`}
        >
          <Check className="h-4 w-4 text-neonGreen" />
          {isBusy ? "Working..." : "Approve"}
        </button>
        <button
          type="button"
          className="glass-button flex items-center gap-1"
          onClick={() => onReject(candidate.candidate_id)}
          disabled={isBusy}
          data-testid={`reject-candidate-${candidate.candidate_id}`}
        >
          <X className="h-4 w-4 text-pink-500" /> Decline & Find Another
        </button>
        <button type="button" className="glass-button flex items-center gap-1" onClick={() => onMoveUp(candidate.candidate_id)}>
          <ArrowUp className="h-4 w-4" /> Up
        </button>
        <button type="button" className="glass-button flex items-center gap-1" onClick={() => onMoveDown(candidate.candidate_id)}>
          <ArrowDown className="h-4 w-4" /> Down
        </button>
        <button type="button" className="glass-button flex items-center gap-1">
          <Replace className="h-4 w-4" /> Replace
        </button>
          </>
        )}
      </div>
    </div>
  );
}
