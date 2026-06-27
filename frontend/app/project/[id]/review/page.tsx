"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AgentTracePanel } from "@/components/AgentTracePanel";
import { ApprovalControls } from "@/components/ApprovalControls";
import { MemoryPanel } from "@/components/MemoryPanel";
import { ProjectShell } from "@/components/ProjectShell";
import { VideoPreview } from "@/components/VideoPreview";
import {
  finalApprove,
  getApiErrorMessage,
  getMemory,
  getProject,
  getTraces,
  regenerate,
  submitTextFeedback,
} from "@/lib/api";
import { resolveOutputMediaUrl } from "@/lib/mediaUrl";
import {
  buildFeedbackMemoryMessage,
  FEEDBACK_SOURCE_STAGE_REVIEW,
  FEEDBACK_TYPE_NEGATIVE,
  FEEDBACK_TYPE_POSITIVE,
} from "@/lib/feedbackMemory";
import { filterTracesForTab } from "@/lib/traceTabFilter";

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = String(params.id);
  const [project, setProject] = useState<Record<string, unknown> | null>(null);
  const [traces, setTraces] = useState([]);
  const [memory, setMemory] = useState<Record<string, unknown>>({ memory_context: {}, memory_updates: [] });
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [memoryMessage, setMemoryMessage] = useState<string | null>(null);

  const refresh = async () => {
    const [projectData, traceData, memoryData] = await Promise.all([
      getProject(projectId),
      getTraces(projectId),
      getMemory(projectId),
    ]);
    setProject(projectData);
    setTraces(traceData);
    setMemory(memoryData);
    return memoryData;
  };

  const submitReviewFeedback = async (feedbackText: string, feedbackType: string) => {
    setLoading(true);
    setError(null);
    try {
      await submitTextFeedback(
        projectId,
        feedbackText,
        feedbackType,
        FEEDBACK_SOURCE_STAGE_REVIEW,
      );
      const memoryData = await refresh();
      const message = buildFeedbackMemoryMessage(
        (memoryData.memory_updates as Array<Record<string, unknown>>) || [],
      );
      setMemoryMessage(message);
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Feedback failed"));
    } finally {
      setLoading(false);
    }
  };

  const handleFeedbackSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!feedback.trim()) {
      return;
    }
    await submitReviewFeedback(feedback.trim(), "text_feedback");
    setFeedback("");
  };

  const handlePositiveFeedback = async () => {
    await submitReviewFeedback(
      "Final output looks good — keep this pacing, caption density, and rank reveal style",
      FEEDBACK_TYPE_POSITIVE,
    );
  };

  const handleNegativeFeedback = async () => {
    await submitReviewFeedback(
      "Output needs improvement — fix story mismatches and tighten rank transitions",
      FEEDBACK_TYPE_NEGATIVE,
    );
  };

  const handleRegenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      if (feedback.trim()) {
        await submitTextFeedback(
          projectId,
          feedback.trim(),
          FEEDBACK_TYPE_NEGATIVE,
          FEEDBACK_SOURCE_STAGE_REVIEW,
        );
      }
      await regenerate(projectId);
      const memoryData = await refresh();
      const message = buildFeedbackMemoryMessage(
        (memoryData.memory_updates as Array<Record<string, unknown>>) || [],
      );
      setMemoryMessage(message);
      setFeedback("");
    } catch (regenError) {
      setError(getApiErrorMessage(regenError, "Regeneration failed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, [projectId]);

  const handleFinalApprove = async () => {
    setLoading(true);
    try {
      await finalApprove(projectId);
      router.push(`/project/${projectId}/comparison`);
    } catch (approveError) {
      setError(getApiErrorMessage(approveError, "Final approve failed"));
    } finally {
      setLoading(false);
    }
  };

  const displayTraces = filterTracesForTab(traces, "review");

  return (
    <ProjectShell active="review">
      <div className="grid gap-6 lg:grid-cols-[280px_1fr_280px]">
        <AgentTracePanel
          traces={displayTraces}
          agentMessages={(project?.agent_messages as never[]) || []}
        />
        <div className="space-y-6">
          <div className="glass-card">
            <h1 className="text-3xl font-bold">Review Output</h1>
            <p className="mt-2 text-slate-400">
              Share what worked or what to improve. Feedback is classified and stored in EditDNA memory for the next run.
            </p>
          </div>
          <VideoPreview
            title="Generated Ranking Video"
            src={resolveOutputMediaUrl(projectId, project?.output_video_path as string | undefined)}
          />
          <form className="glass-card space-y-4" onSubmit={handleFeedbackSubmit} data-testid="review-feedback-form">
            <label className="block text-sm text-slate-400">Your feedback</label>
            <textarea
              className="glass-input min-h-[120px]"
              value={feedback}
              onChange={(event) => setFeedback(event.target.value)}
              placeholder="Make number 1 more dramatic. Use real demo footage."
              data-testid="review-feedback-input"
            />
            {memoryMessage && (
              <p className="text-sm text-neonGreen" data-testid="review-memory-message">
                {memoryMessage}
              </p>
            )}
            {error && <p className="text-sm text-pink-400">{error}</p>}
            <div className="flex flex-wrap gap-3">
              <button type="submit" className="glass-button" disabled={loading || !feedback.trim()}>
                Submit Feedback
              </button>
              <button
                type="button"
                className="glass-button bg-neonGreen/20"
                disabled={loading}
                data-testid="review-positive-feedback"
                onClick={handlePositiveFeedback}
              >
                Looks Good
              </button>
              <button
                type="button"
                className="glass-button bg-pink-500/20"
                disabled={loading}
                data-testid="review-negative-feedback"
                onClick={handleNegativeFeedback}
              >
                Needs Improvement
              </button>
            </div>
          </form>
          <ApprovalControls
            approveLabel="Final Approve"
            onApprove={handleFinalApprove}
            rejectLabel="Regenerate With Feedback"
            onReject={handleRegenerate}
            disabled={loading}
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
