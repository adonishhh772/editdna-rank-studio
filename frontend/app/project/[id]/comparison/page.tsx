"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AgentTracePanel } from "@/components/AgentTracePanel";
import { MemoryPanel } from "@/components/MemoryPanel";
import { ProjectShell } from "@/components/ProjectShell";
import { ScoreCard } from "@/components/ScoreCard";
import { VideoPreview } from "@/components/VideoPreview";
import { getComparison, getMemory, getProject, getTraces } from "@/lib/api";
import { resolveOutputMediaUrl, resolveReferenceMediaUrl } from "@/lib/mediaUrl";

export default function ComparisonPage() {
  const params = useParams();
  const projectId = String(params.id);
  const [project, setProject] = useState<Record<string, unknown> | null>(null);
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);
  const [traces, setTraces] = useState([]);
  const [memory, setMemory] = useState<Record<string, unknown>>({ memory_context: {}, memory_updates: [] });

  useEffect(() => {
    Promise.all([getProject(projectId), getComparison(projectId), getTraces(projectId), getMemory(projectId)]).then(
      ([projectData, comparisonData, traceData, memoryData]) => {
        setProject(projectData);
        setComparison(comparisonData);
        setTraces(traceData);
        setMemory(memoryData);
      },
    );
  }, [projectId]);

  const referencePreviewUrl = resolveReferenceMediaUrl(
    projectId,
    project?.reference_video_path as string | undefined,
    project?.reference_video_url as string | undefined,
  );
  const outputPreviewUrl = resolveOutputMediaUrl(
    projectId,
    project?.output_video_path as string | undefined,
  );

  return (
    <ProjectShell active="comparison">
      <div className="grid gap-6 lg:grid-cols-[280px_1fr_280px]">
        <AgentTracePanel traces={traces} />
        <div className="space-y-6">
          <div className="glass-card">
            <h1 className="text-3xl font-bold">Reference vs Generated</h1>
            <p className="mt-2 text-slate-400">Comparison scores, improvements, and learned preferences.</p>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            <VideoPreview title="Reference" src={referencePreviewUrl} />
            <VideoPreview title="Generated" src={outputPreviewUrl} />
          </div>
          {comparison && (
            <>
              <div className="grid gap-4 md:grid-cols-3">
                <ScoreCard label="Reference match" score={Number(comparison.reference_match_score || 0)} />
                <ScoreCard label="User preference" score={Number(comparison.user_preference_match_score || 0)} />
                <ScoreCard label="Topic relevance" score={Number(comparison.topic_relevance_score || 0)} />
                <ScoreCard label="Pacing match" score={Number(comparison.pacing_match_score || 0)} />
                <ScoreCard label="Caption style" score={Number(comparison.caption_style_match_score || 0)} />
                <ScoreCard label="Ranking structure" score={Number(comparison.ranking_structure_match_score || 0)} />
              </div>
              <div className="glass-card grid gap-6 md:grid-cols-2">
                <ListBlock title="Issues" items={(comparison.issues as string[]) || []} />
                <ListBlock title="Improvements after feedback" items={(comparison.improvements_after_feedback as string[]) || []} />
                <ListBlock title="Learned preferences" items={(comparison.learned_preferences as string[]) || []} />
              </div>
            </>
          )}
        </div>
        <MemoryPanel
          memoryContext={memory.memory_context as Record<string, unknown>}
          memoryUpdates={memory.memory_updates as Array<Record<string, unknown>>}
        />
      </div>
    </ProjectShell>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-400">{title}</h3>
      <ul className="space-y-2 text-sm text-slate-300">
        {items.length === 0 && <li className="text-slate-500">None yet.</li>}
        {items.map((item) => (
          <li key={item}>- {item}</li>
        ))}
      </ul>
    </div>
  );
}
