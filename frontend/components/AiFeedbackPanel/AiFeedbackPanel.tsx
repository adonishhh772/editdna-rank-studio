"use client";

import { Bot, Sparkles } from "lucide-react";
import {
  readAiFeedbackSuggestions,
  severityClassName,
  type AiFeedbackSuggestion,
} from "@/lib/editPlanAiFeedback";

type AiFeedbackPanelProps = {
  editPlan: Record<string, unknown> | null;
  onApplySuggestion: (suggestion: AiFeedbackSuggestion) => void;
  disabled?: boolean;
};

export function AiFeedbackPanel({
  editPlan,
  onApplySuggestion,
  disabled = false,
}: AiFeedbackPanelProps) {
  const suggestions = readAiFeedbackSuggestions(editPlan);

  if (suggestions.length === 0) {
    return (
      <div className="glass-card border-neonPurple/20" data-testid="ai-feedback-panel">
        <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-neonPurple">
          <Bot className="h-4 w-4" />
          AI Edit Feedback
        </h3>
        <p className="mt-2 text-sm text-slate-400">
          The story agent has no open issues for this edit plan. Approve when you are ready to render.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-card border-neonPurple/20" data-testid="ai-feedback-panel">
      <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-neonPurple">
        <Bot className="h-4 w-4" />
        AI Edit Feedback
      </h3>
      <p className="mt-2 text-sm text-slate-400">
        Generated from clip analysis and story coherence checks. Apply a suggestion to store it in memory and regenerate the plan.
      </p>
      <ul className="mt-4 space-y-3">
        {suggestions.map((suggestion) => (
          <li
            key={suggestion.suggestion_id}
            className={`rounded-xl border p-4 ${severityClassName(suggestion.severity)}`}
            data-testid={`ai-feedback-suggestion-${suggestion.suggestion_id}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="flex items-center gap-2 text-sm font-semibold">
                  <Sparkles className="h-4 w-4 text-neonPurple" />
                  {suggestion.label}
                </p>
                <p className="mt-2 text-sm opacity-90">{suggestion.feedback_text}</p>
              </div>
              <button
                type="button"
                className="glass-button text-xs"
                disabled={disabled}
                data-testid={`apply-ai-feedback-${suggestion.suggestion_id}`}
                onClick={() => onApplySuggestion(suggestion)}
              >
                Apply & Regenerate
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
