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

  return (
    <div className="glass-card" data-testid="timeline-plan">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">Timeline Plan</h3>
      <p className="mb-4 text-lg font-semibold text-neonBlue">{String(editPlan.hook_text || "")}</p>
      <div className="space-y-3">
        {sections.map((section) => (
          <div key={String(section.candidate_id)} className="rounded-xl border border-white/5 bg-black/20 p-3">
            <div className="flex items-center justify-between">
              <span className="font-medium">#{String(section.rank)} {String(section.label_text)}</span>
              <span className="text-xs text-slate-400">
                {String(section.clip_start_sec)}s - {String(section.clip_end_sec)}s
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">{String(section.reason)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
