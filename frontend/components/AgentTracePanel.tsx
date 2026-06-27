"use client";

import { Activity, Bot, CheckCircle2, Clock, Download, Loader2, MessageSquare, Search, XCircle } from "lucide-react";
import { AccordionSection } from "@/components/AccordionSection";
import { resolveAgentMessageText, resolveTraceActivityText } from "@/lib/traceDisplay";
import { resolveUploadMediaUrl } from "@/lib/mediaUrl";

type ToolCall = {
  tool?: string;
  stage?: string;
  concept?: string;
  platform?: string;
  source_url?: string;
  local_file_path?: string;
  error?: string;
  timestamp?: string;
};

type Trace = {
  trace_id?: string;
  agent_name: string;
  agent_id: string;
  status: string;
  input_summary?: string;
  output_summary?: string;
  visible_reasoning?: string;
  error?: string;
  started_at?: string;
  tool_calls?: ToolCall[];
  metadata?: Record<string, unknown>;
};

type DownloadEvent = {
  event_id: string;
  agent_name: string;
  stage: string;
  concept: string;
  platform?: string;
  source_url?: string;
  local_file_path?: string;
  search_query?: string;
  error?: string;
  created_at?: string;
};

type AgentMessage = {
  message_id: string;
  from_agent_name: string;
  from_agent_id: string;
  to_agent_id?: string | null;
  message_type: string;
  domain: string;
  payload?: Record<string, unknown>;
};

type AgentTracePanelProps = {
  traces: Trace[];
  downloadEvents?: DownloadEvent[];
  agentMessages?: AgentMessage[];
};

type TraceGroup = {
  groupType: "swarm" | "single";
  parent?: Trace;
  trace?: Trace;
  children: Trace[];
};

function statusIcon(status: string) {
  if (status === "complete") return <CheckCircle2 className="h-4 w-4 text-neonGreen" />;
  if (status === "failed") return <XCircle className="h-4 w-4 text-pink-500" />;
  if (status === "waiting_for_human") return <Clock className="h-4 w-4 text-amber-400" />;
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-neonBlue" />;
  return <Activity className="h-4 w-4 text-slate-400" />;
}

function conciseStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    search_started: "Searching",
    url_selected: "URL found",
    download_started: "Downloading",
    download_success: "Downloaded",
    download_failed: "Failed",
    skipped: "Skipped",
    trim: "Trimming clip",
    scale: "Scaling clip",
    caption: "Adding caption",
    stitch: "Stitching clips",
    hook: "Adding hook",
    audio: "Mixing audio",
  };
  return labels[stage] || stage.replace(/_/g, " ");
}

const IMPORTANT_DOWNLOAD_STAGES = new Set([
  "search_started",
  "url_selected",
  "download_started",
  "download_success",
  "download_failed",
  "skipped",
]);

function stageIcon(stage: string) {
  if (stage.includes("search")) return <Search className="h-3 w-3 text-neonBlue" />;
  if (stage.includes("download")) return <Download className="h-3 w-3 text-neonPurple" />;
  return <Activity className="h-3 w-3 text-slate-400" />;
}

function messageTypeColor(messageType: string) {
  if (messageType === "conflict") return "text-pink-400";
  if (messageType === "agreement") return "text-neonGreen";
  if (messageType === "routing") return "text-neonPurple";
  if (messageType === "request") return "text-neonBlue";
  return "text-slate-300";
}

function buildTraceGroups(traces: Trace[]): TraceGroup[] {
  const childrenByParent = new Map<string, Trace[]>();
  const swarmParentIds = new Set<string>();

  traces.forEach((trace) => {
    if (trace.metadata?.swarm === true) {
      swarmParentIds.add(trace.agent_id);
    }
    const parentAgentId = trace.metadata?.parent_agent_id;
    if (typeof parentAgentId === "string") {
      const siblings = childrenByParent.get(parentAgentId) || [];
      siblings.push(trace);
      childrenByParent.set(parentAgentId, siblings);
    }
  });

  const groups: TraceGroup[] = [];
  traces.forEach((trace) => {
    const parentAgentId = trace.metadata?.parent_agent_id;
    if (typeof parentAgentId === "string" && swarmParentIds.has(parentAgentId)) {
      return;
    }
    if (trace.metadata?.swarm === true) {
      groups.push({
        groupType: "swarm",
        parent: trace,
        children: childrenByParent.get(trace.agent_id) || [],
      });
      return;
    }
    groups.push({
      groupType: "single",
      trace,
      children: [],
    });
  });

  return groups;
}

function TraceCard({ trace, depth = 0 }: { trace: Trace; depth?: number }) {
  const activityText = resolveTraceActivityText(trace);
  const showOutputSummary =
    trace.output_summary?.trim() &&
    trace.output_summary.trim() !== activityText;

  return (
    <div
      className="rounded-xl border border-white/5 bg-black/20 p-3"
      style={{ marginLeft: `${depth * 12}px` }}
      data-testid={depth > 0 ? "swarm-child-trace" : "agent-trace-item"}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          {statusIcon(trace.status)}
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-100">{trace.agent_name}</p>
            <p className="truncate text-xs text-slate-400">{activityText}</p>
          </div>
        </div>
        <span className="shrink-0 text-xs uppercase tracking-wider text-slate-500">{trace.status}</span>
      </div>
      {showOutputSummary && <p className="mt-2 text-xs text-slate-400">{trace.output_summary}</p>}
      {trace.tool_calls && trace.tool_calls.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-slate-500" data-testid="trace-tool-calls">
          {trace.tool_calls.slice(-3).map((toolCall, toolIndex) => (
            <li key={`${trace.trace_id}-tool-${toolIndex}`}>
              {toolCall.stage || toolCall.tool}
              {toolCall.platform ? ` · ${toolCall.platform}` : ""}
              {toolCall.source_url ? ` · ${String(toolCall.source_url).slice(0, 48)}` : ""}
            </li>
          ))}
        </ul>
      )}
      {trace.error && <p className="mt-2 text-xs text-pink-400">{trace.error}</p>}
    </div>
  );
}

export function AgentTracePanel({ traces, downloadEvents = [], agentMessages = [] }: AgentTracePanelProps) {
  const filteredDownloads = downloadEvents.filter((event) => IMPORTANT_DOWNLOAD_STAGES.has(event.stage));
  const demoDownload = [...downloadEvents]
    .reverse()
    .find((event) => event.stage === "download_success" && event.local_file_path);
  const demoPreviewUrl = resolveUploadMediaUrl(demoDownload?.local_file_path);
  const traceGroups = buildTraceGroups(traces);
  const swarmGroupCount = traceGroups.filter((group) => group.groupType === "swarm").length;

  return (
    <aside className="glass-card flex max-h-[calc(100vh-8rem)] flex-col" data-testid="agent-trace-panel">
      <div className="mb-4 flex items-center gap-2">
        <Bot className="h-5 w-5 text-neonPurple" />
        <h2 className="text-lg font-semibold tracking-wide">Live Activity</h2>
      </div>

      <div className="space-y-3 overflow-y-auto pr-1">
        {swarmGroupCount > 0 && (
          <p className="text-xs text-slate-400" data-testid="swarm-trace-summary">
            {swarmGroupCount} agent swarm{swarmGroupCount === 1 ? "" : "s"} — expand to inspect sub-agents.
          </p>
        )}

        {demoPreviewUrl && (
          <section
            className="rounded-xl border border-neonGreen/20 bg-neonGreen/5 p-3"
            data-testid="demo-video-preview"
          >
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-neonGreen">Downloaded Clip</h3>
            <video className="w-full rounded-lg border border-white/10" controls preload="metadata" src={demoPreviewUrl} />
            {demoDownload?.concept && <p className="mt-2 text-xs text-slate-400">{demoDownload.concept}</p>}
          </section>
        )}

        {agentMessages.length > 0 && (
          <AccordionSection
            title="Expert Reasoning"
            icon={<MessageSquare className="h-3 w-3 text-neonPurple" />}
            badge={String(agentMessages.length)}
            defaultOpen
            testId="moe-message-panel"
            contentClassName="max-h-44 overflow-y-auto space-y-2"
          >
            {agentMessages.slice(-14).map((message) => (
              <div key={message.message_id} className="rounded-lg border border-white/5 bg-black/20 p-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className={`font-medium ${messageTypeColor(message.message_type)}`}>
                    {message.message_type}
                  </span>
                  <span className="text-slate-500">{message.domain}</span>
                </div>
                <p className="mt-1 text-slate-300">{resolveAgentMessageText(message)}</p>
              </div>
            ))}
          </AccordionSection>
        )}

        {filteredDownloads.length > 0 && (
          <AccordionSection
            title="Video Fetch"
            icon={<Download className="h-3 w-3 text-neonBlue" />}
            badge={String(filteredDownloads.length)}
            defaultOpen
            testId="download-trace-panel"
            contentClassName="max-h-40 overflow-y-auto space-y-2"
          >
            {filteredDownloads.slice(-12).map((event) => (
              <div key={event.event_id} className="rounded-lg border border-white/5 bg-black/20 p-2 text-xs">
                <div className="flex items-center gap-2 text-slate-300">
                  {stageIcon(event.stage)}
                  <span className="font-medium">{conciseStageLabel(event.stage)}</span>
                </div>
                <p className="mt-1 text-slate-400">{event.concept}</p>
                {event.platform && <p className="text-slate-500">{event.platform}</p>}
                {event.error && <p className="text-pink-400">{event.error}</p>}
              </div>
            ))}
          </AccordionSection>
        )}

        {traces.length === 0 && <p className="text-sm text-slate-400">No agent activity yet.</p>}

        {traceGroups.map((group, groupIndex) => {
          if (group.groupType === "swarm" && group.parent) {
            const parent = group.parent;
            const childCount = group.children.length;
            return (
              <AccordionSection
                key={parent.trace_id || `${parent.agent_id}-swarm-${groupIndex}`}
                title={parent.agent_name}
                icon={statusIcon(parent.status)}
                badge={childCount > 0 ? String(childCount) : undefined}
                defaultOpen={parent.status === "running"}
                testId="swarm-trace-panel"
                contentClassName="max-h-52 overflow-y-auto space-y-2"
              >
                <TraceCard trace={parent} />
                {group.children.map((childTrace, childIndex) => (
                  <TraceCard
                    key={childTrace.trace_id || `${childTrace.agent_id}-child-${childIndex}`}
                    trace={childTrace}
                    depth={1}
                  />
                ))}
              </AccordionSection>
            );
          }

          if (group.trace) {
            return (
              <TraceCard
                key={group.trace.trace_id || `${group.trace.agent_id}-${groupIndex}`}
                trace={group.trace}
              />
            );
          }

          return null;
        })}
      </div>
    </aside>
  );
}
