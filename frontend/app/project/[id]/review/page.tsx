"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AgentTracePanel } from "@/components/AgentTracePanel";
import { ApprovalControls } from "@/components/ApprovalControls";
import { MemoryPanel } from "@/components/MemoryPanel";
import { ProjectShell } from "@/components/ProjectShell";
import { VideoPreview } from "@/components/VideoPreview";
import { finalApprove, getMemory, getProject, getTraces, regenerate, submitTextFeedback } from "@/lib/api";

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
    refresh();
  }, [projectId]);

  const handleFeedbackSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await submitTextFeedback(projectId, feedback);
      await refresh();
      setFeedback("");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Feedback failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    setLoading(true);
    try {
      await regenerate(projectId);
      await refresh();
    } catch (regenError) {
      setError(regenError instanceof Error ? regenError.message : "Regeneration failed");
    } finally {
      setLoading(false);
    }
  };

  const handleFinalApprove = async () => {
    setLoading(true);
    try {
      await finalApprove(projectId);
      router.push(`/project/${projectId}/comparison`);
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "Final approve failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ProjectShell active="review">
      <div className="grid gap-6 lg:grid-cols-[280px_1fr_280px]">
        <AgentTracePanel
          traces={traces}
          agentMessages={(project?.agent_messages as never[]) || []}
        />
        <div className="space-y-6">
          <div className="glass-card">
            <h1 className="text-3xl font-bold">Review Output</h1>
            <p className="mt-2 text-slate-400">Give text or voice feedback, regenerate, or final approve.</p>
          </div>
          <VideoPreview title="Generated Ranking Video" src={`http://127.0.0.1:8000/api/projects/${projectId}/media/output`} />
          <form className="glass-card space-y-4" onSubmit={handleFeedbackSubmit}>
            <label className="block text-sm text-slate-400">Text feedback</label>
            <textarea
              className="glass-input min-h-[120px]"
              value={feedback}
              onChange={(event) => setFeedback(event.target.value)}
              placeholder="Make number 1 more dramatic. Use real demo footage."
            />
            {error && <p className="text-sm text-pink-400">{error}</p>}
            <button type="submit" className="glass-button" disabled={loading || !feedback.trim()}>
              Submit Feedback
            </button>
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
