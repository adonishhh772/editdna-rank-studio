"use client";

import { Film, Lightbulb, Sparkles } from "lucide-react";
import {
  buildEditVideoInsightsFromSections,
  type CandidateVideoInsight,
  type EditVideoInsights,
  type ReferenceVideoInsight,
  type VideoAnalysisScore,
} from "@/lib/videoAnalysisDisplay";

type VideoEditInsightsProps = {
  editPlan: Record<string, unknown> | null;
};

const ACCENT_TEXT_CLASSES: Record<NonNullable<VideoAnalysisScore["accent"]>, string> = {
  blue: "text-neonBlue",
  purple: "text-neonPurple",
  green: "text-neonGreen",
  teal: "text-teal-400",
  orange: "text-amber-400",
  pink: "text-pink-400",
};

export function VideoEditInsights({ editPlan }: VideoEditInsightsProps) {
  const insights = buildEditVideoInsightsFromSections(editPlan);

  if (!insights.reference && insights.candidates.length === 0) {
    return (
      <div className="glass-card" data-testid="video-edit-insights">
        <p className="text-sm text-slate-400">Video analysis insights will appear here after the edit plan is generated.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="video-edit-insights">
      <div className="glass-card border-neonBlue/20">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-neonBlue">
          <Lightbulb className="h-4 w-4" />
          Video Analysis Insights
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          Saved analysis from reference and candidate videos drives clip selection, captions, and motion in this edit plan.
        </p>
      </div>

      {insights.reference && <ReferenceInsightPanel reference={insights.reference} />}
      {insights.candidates.length > 0 && <CandidateInsightsPanel candidates={insights.candidates} />}
    </div>
  );
}

function ReferenceInsightPanel({ reference }: { reference: ReferenceVideoInsight }) {
  return (
    <section className="glass-card" data-testid="reference-edit-insights">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
        <Sparkles className="h-4 w-4 text-neonPurple" />
        Reference Video Analysis
      </h3>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <InsightMetric label="Hook Style" value={reference.hookStyle} accent="purple" />
        <InsightMetric label="Rank Reveal" value={reference.rankRevealStyle} accent="teal" />
        <InsightMetric label="Rank Count" value={String(reference.rankingCount)} accent="blue" />
        <InsightMetric
          label="Avg Segment"
          value={`${reference.averageItemDurationSec.toFixed(1)}s`}
          accent="orange"
        />
        <InsightMetric label="#1 Drama" value={reference.finalRankDramaLevel} accent="pink" />
        <InsightMetric label="Aspect" value={reference.aspectRatio} accent="green" />
      </div>
    </section>
  );
}

function CandidateInsightsPanel({ candidates }: { candidates: CandidateVideoInsight[] }) {
  return (
    <section>
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
        <Film className="h-4 w-4 text-neonBlue" />
        Candidate Clip Analysis
        <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-slate-400">
          {candidates.length}
        </span>
      </h3>
      <div className="space-y-3">
        {candidates.map((candidate) => (
          <CandidateInsightCard key={candidate.candidateId} candidate={candidate} />
        ))}
      </div>
    </section>
  );
}

function CandidateInsightCard({ candidate }: { candidate: CandidateVideoInsight }) {
  const primaryInsight = candidate.highlightReason || candidate.reason;

  return (
    <div
      className="rounded-xl border border-white/5 bg-black/20 p-4"
      data-testid={`candidate-insight-${candidate.candidateId}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="rounded-full bg-neonBlue/20 px-2 py-0.5 text-xs font-bold text-neonBlue">
            #{candidate.rank}
          </span>
          <h4 className="mt-2 font-semibold">{candidate.title}</h4>
          {candidate.sourceVideoTitle && candidate.sourceVideoTitle !== candidate.title && (
            <p className="text-xs text-slate-500">Source: {candidate.sourceVideoTitle}</p>
          )}
          <p className="text-sm text-slate-400">{candidate.concept}</p>
        </div>
        <span className="text-xs font-medium text-teal-400">{candidate.clipRange}</span>
      </div>

      {candidate.voiceoverText && (
        <p className="mt-3 text-sm text-neonPurple">Voiceover: {candidate.voiceoverText}</p>
      )}

      {primaryInsight && (
        <p className="mt-3 rounded-lg bg-neonBlue/10 px-3 py-2 text-sm text-slate-200">{primaryInsight}</p>
      )}

      {candidate.needsImprovement && (
        <p className="mt-2 text-xs font-semibold uppercase tracking-wider text-amber-400">
          Story needs improvement
        </p>
      )}

      {candidate.scores.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {candidate.scores.map((score) => (
            <ScoreBadge key={score.key} score={score} />
          ))}
        </div>
      )}
    </div>
  );
}

function InsightMetric({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: NonNullable<VideoAnalysisScore["accent"]>;
}) {
  return (
    <div className="rounded-xl border border-white/5 bg-black/20 p-3">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${ACCENT_TEXT_CLASSES[accent]}`}>{value}</p>
    </div>
  );
}

function ScoreBadge({ score }: { score: VideoAnalysisScore }) {
  const accentClass = score.accent ? ACCENT_TEXT_CLASSES[score.accent] : "text-slate-200";
  return (
    <div className="rounded-lg bg-white/5 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{score.label}</p>
      <p className={`mt-1 text-sm font-semibold ${accentClass}`}>{Math.round(score.value * 100)}%</p>
    </div>
  );
}
