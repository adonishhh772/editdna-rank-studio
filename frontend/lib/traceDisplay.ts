type TraceLike = {
  visible_reasoning?: string;
  output_summary?: string;
  input_summary?: string;
};

type AgentMessageLike = {
  message_type: string;
  domain: string;
  payload?: Record<string, unknown>;
};

export function resolveTraceActivityText(trace: TraceLike): string {
  if (trace.visible_reasoning?.trim()) {
    return trace.visible_reasoning.trim();
  }
  if (trace.output_summary?.trim()) {
    return trace.output_summary.trim();
  }
  if (trace.input_summary?.trim()) {
    return trace.input_summary.trim();
  }
  return "Working...";
}

export function resolveAgentMessageText(message: AgentMessageLike): string {
  const payload = message.payload ?? {};

  const reasoning = payload.reasoning;
  if (typeof reasoning === "string" && reasoning.trim()) {
    return reasoning.trim();
  }

  const note = payload.note;
  if (typeof note === "string" && note.trim()) {
    return note.trim();
  }

  const summary = payload.summary;
  if (typeof summary === "string" && summary.trim()) {
    return summary.trim();
  }

  const hookText = payload.hook_text;
  if (typeof hookText === "string" && hookText.trim()) {
    return hookText.trim();
  }

  return `${message.message_type} · ${message.domain}`;
}
