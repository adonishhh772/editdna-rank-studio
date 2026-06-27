export const FEEDBACK_TYPE_AI_SUGGESTED = "ai_suggested_feedback";
export const FEEDBACK_TYPE_POSITIVE = "positive_feedback";
export const FEEDBACK_TYPE_NEGATIVE = "negative_feedback";
export const FEEDBACK_TYPE_TEXT = "text_feedback";

export const FEEDBACK_SOURCE_STAGE_STUDIO = "studio";
export const FEEDBACK_SOURCE_STAGE_REVIEW = "review";

export function buildFeedbackMemoryMessage(
  memoryUpdates: Array<Record<string, unknown>>,
): string | null {
  if (memoryUpdates.length === 0) {
    return null;
  }
  const latest = memoryUpdates[memoryUpdates.length - 1];
  const summary = String(latest.summary || "");
  if (!summary) {
    return null;
  }
  return summary;
}
