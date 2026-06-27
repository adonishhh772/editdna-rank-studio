const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type WorkflowTrace = {
  trace_id?: string;
  agent_name: string;
  agent_id: string;
  status: string;
  input_summary?: string;
  output_summary?: string;
  visible_reasoning?: string;
  error?: string;
  tool_calls?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
};

export type WorkflowDownloadEvent = {
  event_id: string;
  agent_name: string;
  stage: string;
  concept: string;
  platform?: string;
  source_url?: string;
  error?: string;
};

export type WorkflowAgentMessage = {
  message_id: string;
  from_agent_name: string;
  from_agent_id: string;
  to_agent_id?: string | null;
  message_type: string;
  domain: string;
  payload?: Record<string, unknown>;
};

export type WorkflowStreamEvent = {
  type: "progress" | "node_complete" | "complete" | "error";
  stage?: string;
  node?: string;
  node_label?: string;
  traces?: WorkflowTrace[];
  download_events?: WorkflowDownloadEvent[];
  agent_messages?: WorkflowAgentMessage[];
  running_trace?: WorkflowTrace | null;
  active_reasoning?: string | null;
  blackboard?: Record<string, unknown>;
  memory_context?: Record<string, unknown>;
  memory_updates?: Array<Record<string, unknown>>;
  learning_preferences?: Record<string, unknown>;
  detail?: string;
};

function parseSseChunk(chunk: string): WorkflowStreamEvent[] {
  const events: WorkflowStreamEvent[] = [];
  for (const line of chunk.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) {
      continue;
    }
    const payload = trimmed.slice(5).trim();
    if (!payload) {
      continue;
    }
    events.push(JSON.parse(payload) as WorkflowStreamEvent);
  }
  return events;
}

export async function runWorkflowStream(
  path: string,
  onEvent: (event: WorkflowStreamEvent) => void,
  body: Record<string, unknown> = {},
): Promise<Record<string, unknown> | null> {
  const separator = path.includes("?") ? "&" : "?";
  const response = await fetch(`${API_BASE}${path}${separator}stream=true`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    const detail = (errorPayload as { detail?: string }).detail;
    throw new Error(detail || `Workflow request failed (${response.status})`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Workflow stream returned no body");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let finalBoard: Record<string, unknown> | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const events = parseSseChunk(part);
      for (const event of events) {
        onEvent(event);
        if (event.type === "complete" && event.blackboard) {
          finalBoard = event.blackboard;
        }
        if (event.type === "error") {
          throw new Error(event.detail || "Workflow failed");
        }
      }
    }
  }

  if (buffer.trim()) {
    const events = parseSseChunk(buffer);
    for (const event of events) {
      onEvent(event);
      if (event.type === "complete" && event.blackboard) {
        finalBoard = event.blackboard;
      }
      if (event.type === "error") {
        throw new Error(event.detail || "Workflow failed");
      }
    }
  }

  return finalBoard;
}
