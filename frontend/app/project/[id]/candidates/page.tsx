"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AgentTracePanel } from "@/components/AgentTracePanel";
import { ApprovalControls } from "@/components/ApprovalControls";
import { CandidateCard } from "@/components/CandidateCard";
import { LearningPreferencesPanel } from "@/components/LearningPreferencesPanel";
import { MemoryPanel } from "@/components/MemoryPanel";
import { ProjectShell } from "@/components/ProjectShell";
import { WorkflowProgressBanner } from "@/components/WorkflowProgressBanner";
import { useWorkflowStream } from "@/hooks/useWorkflowStream";
import {
  getCandidateReviewStatus,
  getDownloadEvents,
  getMemory,
  getProject,
  getTraces,
} from "@/lib/api";
import {
  continueReviewUntilReady,
  REVIEW_STATUS_AWAITING_APPROVAL,
} from "@/lib/candidateReviewFlow";

type Candidate = {
  candidate_id: string;
  title: string;
  concept: string;
  reason: string;
  status?: string;
  recommended_rank?: number;
  topic_match_score: number;
  reference_style_fit_score: number;
  overall_score: number;
  local_file_path?: string;
  source_url?: string;
};

type ReviewStatus = {
  review_active: boolean;
  total_slots: number;
  approved_count: number;
  pending_count: number;
  exhausted_count: number;
  current_slot_rank?: number | null;
  current_status?: string | null;
  current_candidate?: Candidate | null;
  message?: string;
};

export default function CandidatesPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = String(params.id);
  const workflowStream = useWorkflowStream();
  const [project, setProject] = useState<Record<string, unknown> | null>(null);
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus | null>(null);
  const [traces, setTraces] = useState([]);
  const [downloadEvents, setDownloadEvents] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<string | null>(null);
  const [memory, setMemory] = useState<Record<string, unknown>>({ memory_context: {}, memory_updates: [] });
  const [isPreparing, setIsPreparing] = useState(false);
  const [actionCandidateId, setActionCandidateId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [projectData, traceData, memoryData, downloadData, statusData] = await Promise.all([
      getProject(projectId),
      getTraces(projectId),
      getMemory(projectId),
      getDownloadEvents(projectId),
      getCandidateReviewStatus(projectId),
    ]);
    setProject(projectData);
    setTraces(traceData);
    setMemory(memoryData);
    setDownloadEvents(downloadData);
    setReviewStatus(statusData);
  }, [projectId]);

  const fetchReviewStatus = useCallback(
    () => getCandidateReviewStatus(projectId),
    [projectId],
  );

  const runWorkflowPath = useCallback(
    (path: string) => workflowStream.run(path),
    [workflowStream],
  );

  const completeReviewAction = useCallback(
    async (endpoint: string) => {
      setIsPreparing(true);
      setError(null);
      try {
        await workflowStream.run(endpoint);
        await continueReviewUntilReady(projectId, runWorkflowPath, fetchReviewStatus);
        await refresh();
      } catch (workflowError) {
        const rawMessage =
          workflowError instanceof Error ? workflowError.message : "Candidate review failed";
        const isTransientGeminiError =
          rawMessage.includes("503") ||
          rawMessage.includes("UNAVAILABLE") ||
          rawMessage.toLowerCase().includes("timed out");
        setError(
          isTransientGeminiError
            ? "Gemini timed out while fetching the next clip. Your decision was saved — use Find topic clip to retry."
            : rawMessage,
        );
        try {
          await refresh();
        } catch {
          // Ignore refresh failures after a workflow error.
        }
      } finally {
        setIsPreparing(false);
      }
    },
    [fetchReviewStatus, projectId, refresh, runWorkflowPath, workflowStream],
  );

  const runReviewWorkflow = useCallback(
    async (endpoint: string) => {
      await completeReviewAction(endpoint);
    },
    [completeReviewAction],
  );

  const prepareReviewSlot = useCallback(async () => {
    await runReviewWorkflow(`/api/projects/${projectId}/candidates/review/start`);
  }, [projectId, runReviewWorkflow]);

  useEffect(() => {
    const bootstrap = async () => {
      setError(null);
      workflowStream.resetStream();

      try {
        const existingProject = await getProject(projectId);
        const reviewQueue = existingProject.candidate_review_queue;
        const hasReviewQueue = Array.isArray(reviewQueue) && reviewQueue.length > 0;

        if (!hasReviewQueue) {
          await workflowStream.run(`/api/projects/${projectId}/candidates/discover`);
        }

        setIsPreparing(true);
        try {
          await continueReviewUntilReady(projectId, runWorkflowPath, fetchReviewStatus);
        } finally {
          setIsPreparing(false);
        }

        await refresh();
      } catch (bootstrapError) {
        setError(bootstrapError instanceof Error ? bootstrapError.message : "Candidate setup failed");
      }
    };
    bootstrap();
  }, [fetchReviewStatus, projectId, refresh, runWorkflowPath, workflowStream]);

  const approvedCandidates = useMemo(
    () => ((project?.approved_candidates as Candidate[]) || []).slice().sort(
      (left, right) => (left.recommended_rank || 99) - (right.recommended_rank || 99),
    ),
    [project],
  );

  const currentCandidate = useMemo(() => {
    if (reviewStatus?.current_status === REVIEW_STATUS_AWAITING_APPROVAL && reviewStatus.current_candidate) {
      return reviewStatus.current_candidate;
    }
    return null;
  }, [reviewStatus]);

  const totalSlots = reviewStatus?.total_slots ?? approvedCandidates.length;
  const approvedCount = reviewStatus?.approved_count ?? approvedCandidates.length;
  const exhaustedCount = reviewStatus?.exhausted_count ?? 0;
  const pendingCount = reviewStatus?.pending_count ?? 0;

  const allSlotsResolved =
    reviewStatus?.review_active === true &&
    pendingCount === 0 &&
    approvedCount + exhaustedCount >= totalSlots &&
    totalSlots > 0;

  const canContinueToStudio =
    !workflowStream.isRunning &&
    !isPreparing &&
    actionCandidateId === null &&
    currentCandidate === null;

  const handleApproveCandidate = async (candidateId: string) => {
    setActionCandidateId(candidateId);
    try {
      await completeReviewAction(`/api/projects/${projectId}/candidates/${candidateId}/approve`);
    } finally {
      setActionCandidateId(null);
    }
  };

  const handleRejectCandidate = async (candidateId: string) => {
    setActionCandidateId(candidateId);
    try {
      await completeReviewAction(`/api/projects/${projectId}/candidates/${candidateId}/reject`);
    } finally {
      setActionCandidateId(null);
    }
  };

  const handleRediscoverCandidates = async () => {
    setError(null);
    workflowStream.resetStream();
    setIsPreparing(true);

    try {
      await workflowStream.run(`/api/projects/${projectId}/candidates/discover`);
      await refresh();
    } catch (rediscoverError) {
      setError(rediscoverError instanceof Error ? rediscoverError.message : "Candidate rediscovery failed");
    } finally {
      setIsPreparing(false);
    }
  };

  const handleSkipSlot = async () => {
    await runReviewWorkflow(`/api/projects/${projectId}/candidates/review/skip`);
  };

  const handleContinueToStudio = () => {
    router.push(`/project/${projectId}/studio`);
  };

  const isLoading = workflowStream.isRunning || isPreparing;
  const displayTraces = workflowStream.traces.length > 0 ? workflowStream.traces : traces;
  const displayDownloads =
    workflowStream.downloadEvents.length > 0 ? workflowStream.downloadEvents : (downloadEvents as never[]);
  const displayMemoryContext =
    Object.keys(workflowStream.memoryContext).length > 0
      ? workflowStream.memoryContext
      : (memory.memory_context as Record<string, unknown>);
  const displayMemoryUpdates =
    workflowStream.memoryUpdates.length > 0
      ? workflowStream.memoryUpdates
      : (memory.memory_updates as Array<Record<string, unknown>>);
  const statusMessage = reviewStatus?.message ?? "";
  const showPreparingState =
    isPreparing || reviewStatus?.current_status === "preparing";
  const topicConceptCount = (
    (project?.topic_research as { candidate_concepts?: string[] } | undefined)?.candidate_concepts ?? []
  ).length;
  const hasPendingSlots =
    pendingCount > 0 || (totalSlots === 0 && topicConceptCount > 0 && !allSlotsResolved);

  return (
    <ProjectShell active="candidates">
      <div className="grid gap-6 lg:grid-cols-[280px_1fr_280px]">
        <AgentTracePanel traces={displayTraces} downloadEvents={displayDownloads} />
        <div className="space-y-6">
          <div className="glass-card">
            <h1 className="text-3xl font-bold">Candidate Approval</h1>
            <p className="mt-2 text-slate-400">
              Approve each clip and the next topic Short is fetched automatically until all slots are filled.
              Skip slots or continue to the studio when you are ready.
            </p>
            {totalSlots > 0 && (
              <p className="mt-2 text-sm text-neonBlue" data-testid="candidate-review-progress">
                {approvedCount} of {totalSlots} approved
                {exhaustedCount > 0 && ` · ${exhaustedCount} skipped`}
                {pendingCount > 0 && ` · ${pendingCount} remaining`}
              </p>
            )}
            {statusMessage && <p className="mt-2 text-sm text-slate-500">{statusMessage}</p>}
          </div>
          {isLoading && (
            <WorkflowProgressBanner
              isRunning={workflowStream.isRunning || isPreparing}
              activeNodeLabel={workflowStream.activeNodeLabel}
              activeReasoning={workflowStream.activeReasoning}
            />
          )}
          {error && <p className="text-pink-400">{error}</p>}
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              className="glass-button text-sm"
              onClick={prepareReviewSlot}
              disabled={isLoading || actionCandidateId !== null || !hasPendingSlots}
              data-testid="find-topic-clip-button"
            >
              Find topic clip
            </button>
            <button
              type="button"
              className="glass-button text-sm"
              onClick={handleSkipSlot}
              disabled={isLoading || actionCandidateId !== null || !hasPendingSlots}
              data-testid="skip-slot-button"
            >
              Skip slot
            </button>
            <button
              type="button"
              className="glass-button text-sm"
              onClick={handleRediscoverCandidates}
              disabled={isLoading || actionCandidateId !== null}
              data-testid="rediscover-candidates-button"
            >
              Re-run Discovery
            </button>
          </div>
          {approvedCandidates.length > 0 && (
            <div className="space-y-3" data-testid="approved-candidates-list">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-neonGreen">Approved</h2>
              {approvedCandidates.map((candidate) => (
                <CandidateCard
                  key={candidate.candidate_id}
                  candidate={candidate}
                  isReadOnly
                  onApprove={() => undefined}
                  onReject={() => undefined}
                  onMoveUp={() => undefined}
                  onMoveDown={() => undefined}
                />
              ))}
            </div>
          )}
          {showPreparingState && !currentCandidate && (
            <div className="glass-card text-slate-400" data-testid="candidate-preparing-state">
              {workflowStream.activeReasoning ||
                "Fetching the next topic Short from YouTube + TikTok..."}
            </div>
          )}
          {currentCandidate ? (
            <div className="space-y-2">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-neonBlue">
                Review Slot #{currentCandidate.recommended_rank ?? reviewStatus?.current_slot_rank}
              </h2>
              <CandidateCard
                key={currentCandidate.candidate_id}
                candidate={currentCandidate}
                isBusy={actionCandidateId === currentCandidate.candidate_id || isPreparing}
                onApprove={handleApproveCandidate}
                onReject={handleRejectCandidate}
                onMoveUp={() => undefined}
                onMoveDown={() => undefined}
              />
            </div>
          ) : (
            !showPreparingState && (
              <div className="glass-card text-slate-400" data-testid="all-candidates-reviewed">
                {allSlotsResolved
                  ? "All slots handled. Continue to the studio or find more topic clips."
                  : hasPendingSlots
                    ? "Click Find topic clip to search Shorts for your topic, or skip slots to move on."
                    : "No candidate ready for review yet."}
              </div>
            )
          )}
          <ApprovalControls
            approveLabel="Continue to Studio"
            onApprove={handleContinueToStudio}
            disabled={!canContinueToStudio}
          />
        </div>
        <div className="space-y-6">
          <LearningPreferencesPanel memoryContext={displayMemoryContext} />
          <MemoryPanel
            memoryContext={displayMemoryContext}
            memoryUpdates={displayMemoryUpdates}
          />
        </div>
      </div>
    </ProjectShell>
  );
}
