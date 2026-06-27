"use client";

import { Loader2 } from "lucide-react";

type WorkflowProgressBannerProps = {
  isRunning: boolean;
  activeNodeLabel?: string | null;
  activeReasoning?: string | null;
};

export function WorkflowProgressBanner({
  isRunning,
  activeNodeLabel,
  activeReasoning,
}: WorkflowProgressBannerProps) {
  if (!isRunning) {
    return null;
  }

  const primaryLabel = activeReasoning || activeNodeLabel || "Running workflow...";
  const showStepLabel =
    activeReasoning && activeNodeLabel && activeReasoning !== activeNodeLabel;

  return (
    <div
      className="glass-card flex items-center gap-3 border-neonBlue/30 bg-neonBlue/10"
      data-testid="workflow-progress-banner"
    >
      <Loader2 className="h-5 w-5 shrink-0 animate-spin text-neonBlue" />
      <div>
        <p className="text-sm font-medium text-slate-100">{primaryLabel}</p>
        {showStepLabel && <p className="mt-1 text-xs text-slate-400">{activeNodeLabel}</p>}
      </div>
    </div>
  );
}
