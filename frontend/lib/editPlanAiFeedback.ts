export type AiFeedbackSuggestion = {
  suggestion_id: string;
  label: string;
  feedback_text: string;
  severity: "info" | "warning" | "critical";
  source: string;
  rank?: number | null;
};

export function readAiFeedbackSuggestions(
  editPlan: Record<string, unknown> | null | undefined,
): AiFeedbackSuggestion[] {
  const rawSuggestions = (editPlan?.ai_feedback_suggestions as AiFeedbackSuggestion[]) || [];
  return rawSuggestions.filter(
    (suggestion) => suggestion.label && suggestion.feedback_text,
  );
}

export function severityClassName(severity: AiFeedbackSuggestion["severity"]): string {
  if (severity === "critical") {
    return "border-pink-500/30 bg-pink-500/10 text-pink-200";
  }
  if (severity === "warning") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-100";
  }
  return "border-neonBlue/20 bg-neonBlue/10 text-slate-200";
}
