"use client";

import { ArrowDown, ArrowUp, Check, Replace, X } from "lucide-react";
import { resolveUploadMediaUrl } from "@/lib/mediaUrl";

type Candidate = {
  candidate_id: string;
  title: string;
  concept: string;
  reason: string;
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
  onApprove: (candidateId: string) => void;
  onReject: (candidateId: string) => void;
  onMoveUp: (candidateId: string) => void;
  onMoveDown: (candidateId: string) => void;
};

export function CandidateCard({
  candidate,
  isBusy = false,
  isReadOnly = false,
  onApprove,
  onReject,
  onMoveUp,
  onMoveDown,
}: CandidateCardProps) {
  const previewUrl = resolveUploadMediaUrl(candidate.local_file_path);

  return (
    <div className="glass-card" data-testid={`candidate-card-${candidate.candidate_id}`}>
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
          <p className="text-xs uppercase tracking-wider text-neonBlue">Rank #{candidate.recommended_rank}</p>
          <h3 className="text-lg font-semibold">{candidate.title}</h3>
          <p className="mt-1 text-sm text-slate-400">{candidate.concept}</p>
        </div>
        <div className="rounded-lg bg-neonPurple/20 px-3 py-1 text-sm font-bold text-neonPurple">
          {(candidate.overall_score * 100).toFixed(0)}
        </div>
      </div>
      <p className="mb-4 text-sm text-slate-300">{candidate.reason}</p>
      {candidate.source_url && !previewUrl && (
        <p className="mb-4 truncate text-xs text-slate-500" title={candidate.source_url}>
          Source: {candidate.source_url}
        </p>
      )}
      <div className="mb-4 grid grid-cols-2 gap-2 text-xs text-slate-400">
        <span>Topic: {(candidate.topic_match_score * 100).toFixed(0)}%</span>
        <span>Style: {(candidate.reference_style_fit_score * 100).toFixed(0)}%</span>
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
