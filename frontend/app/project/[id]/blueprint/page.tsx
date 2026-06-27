"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AgentTracePanel } from "@/components/AgentTracePanel";
import { MemoryPanel } from "@/components/MemoryPanel";
import { ProjectShell } from "@/components/ProjectShell";
import { WorkflowProgressBanner } from "@/components/WorkflowProgressBanner";
import { useWorkflowStream } from "@/hooks/useWorkflowStream";
import { getMemory, getProject, getTraces, setTopic } from "@/lib/api";
import { resolveDisplayMemory } from "@/lib/memoryDisplay";
import { resolveReferenceMediaUrl } from "@/lib/mediaUrl";
import {
  filterDownloadEventsForTab,
  filterTracesForTab,
} from "@/lib/traceTabFilter";
import { BlueprintAnalytics } from "@/components/BlueprintAnalytics";
import { VideoPreview } from "@/components/VideoPreview";

export default function BlueprintPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = String(params.id);
  const workflowStream = useWorkflowStream();
  const [project, setProject] = useState<Record<string, unknown> | null>(null);
  const [topic, setTopicValue] = useState("");
  const [traces, setTraces] = useState([]);
  const [memory, setMemory] = useState<Record<string, unknown>>({ memory_context: {}, memory_updates: [] });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getProject(projectId), getTraces(projectId), getMemory(projectId)]).then(
      ([projectData, traceData, memoryData]) => {
        setProject(projectData);
        setTraces(traceData);
        setMemory(memoryData);
        if (typeof projectData.topic === "string") {
          setTopicValue(projectData.topic);
        }
      },
    );
  }, [projectId]);

  const blueprint = (project?.reference_blueprint as Record<string, unknown>) || null;
  const rawTraces = workflowStream.isRunning ? workflowStream.traces : traces;
  const displayTraces = filterTracesForTab(rawTraces, "blueprint");
  const displayDownloads = filterDownloadEventsForTab(
    workflowStream.downloadEvents,
    "blueprint",
  );
  const displayMemory = resolveDisplayMemory(
    {
      memory_context: memory.memory_context as Record<string, unknown>,
      memory_updates: memory.memory_updates as Array<Record<string, unknown>>,
    },
    {
      memory_context: workflowStream.memoryContext,
      memory_updates: workflowStream.memoryUpdates,
    },
  );

  const referencePreviewUrl = resolveReferenceMediaUrl(
    projectId,
    project?.reference_video_path as string | undefined,
    project?.reference_video_url as string | undefined,
  );

  const handleTopicSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    workflowStream.resetStream();

    try {
      await setTopic(projectId, topic);
      await workflowStream.run(`/api/projects/${projectId}/research`);
      router.push(`/project/${projectId}/candidates`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Research failed");
    }
  };

  return (
    <ProjectShell active="blueprint">
      <div className="grid gap-6 lg:grid-cols-[280px_1fr_280px]">
        <AgentTracePanel traces={displayTraces} downloadEvents={displayDownloads} />
        <div className="space-y-6">
          <div className="glass-card">
            <h1 className="text-3xl font-bold">Reference Blueprint</h1>
            {referencePreviewUrl && (
              <div className="mt-6">
                <VideoPreview title="Reference" src={referencePreviewUrl} />
              </div>
            )}
            {blueprint ? (
              <div className="mt-6">
                <BlueprintAnalytics blueprint={blueprint} />
              </div>
            ) : (
              <p className="mt-4 text-slate-400">Reference analysis pending or failed.</p>
            )}
          </div>
          <form className="glass-card space-y-4" onSubmit={handleTopicSubmit}>
            <h2 className="text-xl font-semibold">What ranking video do you want to generate?</h2>
            <input
              className="glass-input"
              placeholder="Top 5 AI video editing tools"
              value={topic}
              onChange={(event) => setTopicValue(event.target.value)}
              required
              disabled={workflowStream.isRunning}
            />
            {workflowStream.isRunning && (
              <WorkflowProgressBanner
                isRunning={workflowStream.isRunning}
                activeNodeLabel={workflowStream.activeNodeLabel}
                activeReasoning={workflowStream.activeReasoning}
              />
            )}
            {error && <p className="text-sm text-pink-400">{error}</p>}
            <button
              type="submit"
              className="glass-button bg-neonPurple/20"
              disabled={workflowStream.isRunning}
            >
              {workflowStream.isRunning ? "Researching topic..." : "Research Topic & Continue"}
            </button>
          </form>
        </div>
        <MemoryPanel
          memoryContext={displayMemory.memory_context}
          memoryUpdates={displayMemory.memory_updates}
        />
      </div>
    </ProjectShell>
  );
}
