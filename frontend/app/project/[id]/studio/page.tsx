"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AgentTracePanel } from "@/components/AgentTracePanel";
import { ApprovalControls } from "@/components/ApprovalControls";
import { MemoryPanel } from "@/components/MemoryPanel";
import { ProjectShell } from "@/components/ProjectShell";
import { TimelinePlan } from "@/components/TimelinePlan";
import { VideoPreview } from "@/components/VideoPreview";
import { WorkflowProgressBanner } from "@/components/WorkflowProgressBanner";
import { useWorkflowStream } from "@/hooks/useWorkflowStream";
import {
  approveEditPlan,
  getMemory,
  getProject,
  getTraces,
  renderVideo,
  submitTextFeedback,
} from "@/lib/api";
import { resolveReferenceMediaUrl } from "@/lib/mediaUrl";

export default function StudioPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = String(params.id);
  const workflowStream = useWorkflowStream();
  const [project, setProject] = useState<Record<string, unknown> | null>(null);
  const [traces, setTraces] = useState([]);
  const [memory, setMemory] = useState<Record<string, unknown>>({ memory_context: {}, memory_updates: [] });
  const [renderLoading, setRenderLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    const [projectData, traceData, memoryData] = await Promise.all([
      getProject(projectId),
      getTraces(projectId),
      getMemory(projectId),
    ]);
    setProject(projectData);
    setTraces(traceData);
    setMemory(memoryData);
  };

  useEffect(() => {
    const bootstrap = async () => {
      setError(null);
      workflowStream.resetStream();

      try {
        const existingProject = await getProject(projectId);
        setProject(existingProject);

        if (existingProject.edit_plan) {
          await refresh();
          return;
        }

        const board = await workflowStream.run(`/api/projects/${projectId}/edit-plan`);
        await refresh();
        if (board?.edit_plan) {
          setProject((current) => ({ ...(current || {}), ...board }));
        }
      } catch (bootstrapError) {
        setError(bootstrapError instanceof Error ? bootstrapError.message : "Edit plan failed");
        await refresh();
      }
    };
    bootstrap();
  }, [projectId]);

  const handleRegenerateEditPlan = async () => {
    setError(null);
    workflowStream.resetStream();

    try {
      const board = await workflowStream.run(`/api/projects/${projectId}/edit-plan`);
      await refresh();
      if (board?.edit_plan) {
        setProject((current) => ({ ...(current || {}), ...board }));
      }
    } catch (regenerateError) {
      setError(regenerateError instanceof Error ? regenerateError.message : "Edit plan regeneration failed");
      await refresh();
    }
  };

  const handleApproveAndRender = async () => {
    setRenderLoading(true);
    setError(null);
    try {
      await approveEditPlan(projectId);
      await renderVideo(projectId);
      router.push(`/project/${projectId}/review`);
    } catch (renderError) {
      setError(renderError instanceof Error ? renderError.message : "Render failed");
    } finally {
      setRenderLoading(false);
    }
  };

  const handleQuickFeedback = async (text: string) => {
    await submitTextFeedback(projectId, text);
    await refresh();
  };

  const isLoading = workflowStream.isRunning || renderLoading;
  const displayTraces = workflowStream.isRunning ? workflowStream.traces : traces;
  const displayMessages = workflowStream.isRunning
    ? workflowStream.agentMessages
    : ((project?.agent_messages as never[]) || []);

  const referencePreviewUrl = resolveReferenceMediaUrl(
    projectId,
    project?.reference_video_path as string | undefined,
    project?.reference_video_url as string | undefined,
  );

  return (
    <ProjectShell active="studio">
      <div className="grid gap-6 lg:grid-cols-[280px_1fr_280px]">
        <AgentTracePanel traces={displayTraces} agentMessages={displayMessages} />
        <div className="space-y-6">
          <div className="glass-card">
            <h1 className="text-3xl font-bold">Edit Studio</h1>
            <p className="mt-2 text-slate-400">Review the edit plan before rendering the ranking video.</p>
          </div>
          {workflowStream.isRunning && (
            <WorkflowProgressBanner
              isRunning={workflowStream.isRunning}
              activeNodeLabel={workflowStream.activeNodeLabel}
              activeReasoning={workflowStream.activeReasoning}
            />
          )}
          {isLoading && !workflowStream.isRunning && <p className="text-slate-400">Rendering video...</p>}
          {error && <p className="text-pink-400">{error}</p>}
          <VideoPreview title="Reference" src={referencePreviewUrl} />
          <div className="flex justify-end">
            <button
              type="button"
              className="glass-button text-sm"
              onClick={handleRegenerateEditPlan}
              disabled={isLoading}
              data-testid="regenerate-edit-plan-button"
            >
              Regenerate Edit Plan
            </button>
          </div>
          <TimelinePlan editPlan={(project?.edit_plan as Record<string, unknown>) || null} />
          <ApprovalControls
            approveLabel="Approve Edit Plan & Render"
            onApprove={handleApproveAndRender}
            disabled={isLoading}
            extraActions={[
              { label: "Fewer captions", onClick: () => handleQuickFeedback("Reduce captions") },
              { label: "More dramatic #1", onClick: () => handleQuickFeedback("Make number 1 more dramatic") },
              { label: "Cleaner audio", onClick: () => handleQuickFeedback("Make the audio cleaner") },
            ]}
          />
        </div>
        <MemoryPanel
          memoryContext={memory.memory_context as Record<string, unknown>}
          memoryUpdates={memory.memory_updates as Array<Record<string, unknown>>}
        />
      </div>
    </ProjectShell>
  );
}
