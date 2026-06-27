"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AgentTracePanel } from "@/components/AgentTracePanel";
import { ApprovalControls } from "@/components/ApprovalControls";
import { MemoryPanel } from "@/components/MemoryPanel";
import { ProjectShell } from "@/components/ProjectShell";
import { TimelinePlan } from "@/components/TimelinePlan";
import { VideoEditInsights } from "@/components/VideoEditInsights";
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
  const [approveLoading, setApproveLoading] = useState(false);
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

        const existingPlan = existingProject.edit_plan as Record<string, unknown> | undefined;
        const needsApproval = Boolean(existingPlan?.needs_human_approval);
        const waitingForHuman = Boolean(existingProject.waiting_for_human);

        if (existingPlan && (!needsApproval || !waitingForHuman)) {
          await refresh();
          return;
        }

        if (existingPlan && needsApproval) {
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

  const handleApproveEditPlan = async () => {
    setApproveLoading(true);
    setError(null);
    try {
      const board = await approveEditPlan(projectId);
      setProject((current) => ({ ...(current || {}), ...board }));
      await refresh();
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "Edit plan approval failed");
    } finally {
      setApproveLoading(false);
    }
  };

  const handleRenderVideo = async () => {
    setRenderLoading(true);
    setError(null);
    try {
      await renderVideo(projectId);
      router.push(`/project/${projectId}/review`);
    } catch (renderError) {
      setError(renderError instanceof Error ? renderError.message : "Render failed");
    } finally {
      setRenderLoading(false);
    }
  };

  const handleApproveAndRender = async () => {
    setApproveLoading(true);
    setRenderLoading(true);
    setError(null);
    try {
      await approveEditPlan(projectId);
      await renderVideo(projectId);
      router.push(`/project/${projectId}/review`);
    } catch (renderError) {
      setError(renderError instanceof Error ? renderError.message : "Render failed");
    } finally {
      setApproveLoading(false);
      setRenderLoading(false);
    }
  };

  const handleQuickFeedback = async (text: string) => {
    await submitTextFeedback(projectId, text);
    await refresh();
  };

  const isLoading = workflowStream.isRunning || renderLoading || approveLoading;
  const editPlan = (project?.edit_plan as Record<string, unknown>) || null;
  const editPlanNeedsApproval = Boolean(editPlan?.needs_human_approval);
  const storyReady = Boolean(editPlan?.story_ready);
  const storyIssues = (editPlan?.story_issues as string[]) || [];
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
            <p className="mt-2 text-slate-400">
              Review the edit plan story, voiceover lines, and rank overlays before rendering.
            </p>
            {editPlan && (
              <p
                className={`mt-2 text-sm font-semibold ${storyReady ? "text-neonGreen" : "text-amber-400"}`}
                data-testid="edit-plan-story-status"
              >
                {editPlanNeedsApproval
                  ? storyReady
                    ? "Edit plan ready — approve the story before rendering."
                    : "Edit plan needs improvement — review story mismatches before approving."
                  : "Edit plan approved — you can render when ready."}
              </p>
            )}
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
          <VideoEditInsights editPlan={editPlan} />
          <VideoPreview title="Reference" src={referencePreviewUrl} />
          {storyIssues.length > 0 && (
            <div className="glass-card border-amber-500/20" data-testid="edit-plan-story-issues">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-amber-400">Story Review</h3>
              <ul className="mt-2 space-y-1 text-sm text-amber-100">
                {storyIssues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
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
          <TimelinePlan editPlan={editPlan} />
          <ApprovalControls
            approveLabel={editPlanNeedsApproval ? "Approve Edit Plan" : "Render Video"}
            onApprove={editPlanNeedsApproval ? handleApproveEditPlan : handleRenderVideo}
            onReject={editPlanNeedsApproval ? handleRegenerateEditPlan : undefined}
            rejectLabel="Regenerate Plan"
            disabled={isLoading}
            extraActions={[
              ...(editPlanNeedsApproval
                ? [{ label: "Approve & Render", onClick: handleApproveAndRender }]
                : []),
              { label: "Fewer captions", onClick: () => handleQuickFeedback("Reduce captions") },
              { label: "More dramatic #1", onClick: () => handleQuickFeedback("Make number 1 more dramatic") },
              { label: "Fix story mismatch", onClick: () => handleQuickFeedback("Fix voiceover and story mismatches") },
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
