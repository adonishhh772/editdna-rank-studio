"use client";

type TimelinePlanProps = {
  editPlan: Record<string, unknown> | null;
};

export function TimelinePlan({ editPlan }: TimelinePlanProps) {
  if (!editPlan) {
    return (
      <div className="glass-card" data-testid="timeline-plan">
        <p className="text-sm text-slate-400">Edit plan not generated yet.</p>
      </div>
    );
  }

  const sections = (editPlan.sections as Array<Record<string, unknown>>) || [];
  const storyIssues = (editPlan.story_issues as string[]) || [];
  const storyReady = Boolean(editPlan.story_ready);

  return (
    <div className="glass-card" data-testid="timeline-plan">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Timeline Plan</h3>
        <span
          className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider ${
            storyReady ? "bg-neonGreen/20 text-neonGreen" : "bg-amber-500/20 text-amber-400"
          }`}
          data-testid="timeline-plan-story-status"
        >
          {storyReady ? "Story ready" : "Needs improvement"}
        </span>
      </div>
      <p className="mb-4 text-lg font-semibold text-neonBlue">{String(editPlan.hook_text || "")}</p>
      {storyIssues.length > 0 && (
        <ul className="mb-4 space-y-1 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-200">
          {storyIssues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      )}
      <div className="space-y-3">
        {sections.map((section) => {
          const momentTitle = String(
            section.video_moment_title || section.title || section.label_text || "Untitled moment",
          );
          const sourceTitle = String(section.source_video_title || "");
          const needsImprovement = Boolean(section.needs_improvement);

          return (
            <div
              key={String(section.candidate_id)}
              className="rounded-xl border border-white/5 bg-black/20 p-3"
              data-testid={`timeline-section-${String(section.rank)}`}
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <span className="font-medium">#{String(section.rank)} {momentTitle}</span>
                  {sourceTitle && sourceTitle !== momentTitle && (
                    <p className="mt-1 text-[11px] text-slate-500">Source: {sourceTitle}</p>
                  )}
                </div>
                <span className="text-xs text-slate-400">
                  {String(section.clip_start_sec)}s - {String(section.clip_end_sec)}s
                </span>
              </div>
              {section.voiceover_text && (
                <p className="mt-2 text-xs text-neonPurple" data-testid={`section-voiceover-${String(section.rank)}`}>
                  Voiceover: {String(section.voiceover_text)}
                </p>
              )}
              <p className="mt-1 text-xs text-slate-400">{String(section.reason)}</p>
              {section.highlight_reason && String(section.highlight_reason) !== String(section.reason) && (
                <p className="mt-1 text-xs text-neonBlue">{String(section.highlight_reason)}</p>
              )}
              {needsImprovement && (
                <p className="mt-2 text-xs font-semibold uppercase tracking-wider text-amber-400">
                  Story needs improvement
                </p>
              )}
              {section.analysis_scores && typeof section.analysis_scores === "object" && (
                <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-wider text-slate-500">
                  {Object.entries(section.analysis_scores as Record<string, unknown>).map(([key, value]) => (
                    <span key={key} className="rounded bg-white/5 px-2 py-1">
                      {key.replace(/_/g, " ")}: {Math.round(Number(value) * 100)}%
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
