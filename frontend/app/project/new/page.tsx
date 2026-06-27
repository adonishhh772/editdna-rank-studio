"use client";

import { FormEvent, useState } from "react";
import { Link2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { AgentTracePanel } from "@/components/AgentTracePanel";
import { MemoryPanel } from "@/components/MemoryPanel";
import { WorkflowProgressBanner } from "@/components/WorkflowProgressBanner";
import { useWorkflowStream } from "@/hooks/useWorkflowStream";
import {
  createProject,
  getApiErrorMessage,
  setReferenceVideoUrl,
  uploadReference,
} from "@/lib/api";
import { resolveDisplayMemory } from "@/lib/memoryDisplay";
import { filterTracesForTab, filterDownloadEventsForTab } from "@/lib/traceTabFilter";
import { validateVideoUrl } from "@/lib/videoUrl";

type ReferenceInputMode = "upload" | "url";

export default function NewProjectPage() {
  const router = useRouter();
  const workflowStream = useWorkflowStream();
  const [title, setTitle] = useState("My Ranking Project");
  const [inputMode, setInputMode] = useState<ReferenceInputMode>("url");
  const [file, setFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleInputModeChange = (mode: ReferenceInputMode) => {
    setInputMode(mode);
    setError(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (inputMode === "upload" && !file) {
      setError("Please upload a reference ranking video.");
      return;
    }

    if (inputMode === "url") {
      const validationError = validateVideoUrl(videoUrl);
      if (validationError) {
        setError(validationError);
        return;
      }
    }

    setError(null);
    workflowStream.resetStream();

    try {
      const project = await createProject(title);
      const projectId = String(project.project_id);

      if (inputMode === "upload" && file) {
        await uploadReference(projectId, file);
      } else {
        await setReferenceVideoUrl(projectId, videoUrl.trim());
      }

      await workflowStream.run(`/api/projects/${projectId}/analyse-reference`);
      router.push(`/project/${projectId}/blueprint`);
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Failed to create project"));
    }
  };

  const isLoading = workflowStream.isRunning;
  const displayTraces = filterTracesForTab(
    workflowStream.traces,
    "reference",
  );
  const displayDownloads = filterDownloadEventsForTab(
    workflowStream.downloadEvents,
    "reference",
  );
  const displayMemory = resolveDisplayMemory(
    { memory_context: {}, memory_updates: [] },
    {
      memory_context: workflowStream.memoryContext,
      memory_updates: workflowStream.memoryUpdates,
    },
  );

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      <div className="grid gap-6 lg:grid-cols-[280px_1fr_280px]">
        <AgentTracePanel traces={displayTraces} downloadEvents={displayDownloads} />

        <div className="glass-card">
          <h1 className="text-3xl font-bold">New Ranking Project</h1>
          <p className="mt-2 text-lg text-slate-400">
            Provide a reference ranking video URL or upload a file to extract its editing DNA.
          </p>

          {isLoading && (
            <div className="mt-6">
              <WorkflowProgressBanner
                isRunning={workflowStream.isRunning}
                activeNodeLabel={workflowStream.activeNodeLabel}
                activeReasoning={workflowStream.activeReasoning}
              />
            </div>
          )}

          <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm text-slate-400">Project title</label>
              <input
                className="glass-input"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="mb-2 block text-sm text-slate-400">Reference video source</label>
              <div className="mb-4 flex gap-2">
                <button
                  type="button"
                  className={`glass-button ${inputMode === "url" ? "bg-neonBlue/20" : ""}`}
                  onClick={() => handleInputModeChange("url")}
                  disabled={isLoading}
                >
                  <Link2 className="mr-2 inline h-4 w-4" />
                  Video URL
                </button>
                <button
                  type="button"
                  className={`glass-button ${inputMode === "upload" ? "bg-neonBlue/20" : ""}`}
                  onClick={() => handleInputModeChange("upload")}
                  disabled={isLoading}
                >
                  <Upload className="mr-2 inline h-4 w-4" />
                  Upload file
                </button>
              </div>

              {inputMode === "url" ? (
                <div>
                  <input
                    className="glass-input"
                    type="url"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={videoUrl}
                    onChange={(event) => setVideoUrl(event.target.value)}
                    data-testid="reference-video-url-input"
                    disabled={isLoading}
                  />
                  <p className="mt-2 text-xs text-slate-500">
                    Supports YouTube, TikTok, Instagram, Vimeo, and direct video links (.mp4, .webm, .mov, .mkv).
                  </p>
                </div>
              ) : (
                <label className="glass-card flex cursor-pointer flex-col items-center justify-center border-dashed py-10">
                  <Upload className="mb-3 h-8 w-8 text-neonBlue" />
                  <span>{file ? file.name : "Click to upload MP4/MOV reference video"}</span>
                  <input
                    type="file"
                    accept="video/*"
                    className="hidden"
                    onChange={(event) => setFile(event.target.files?.[0] || null)}
                    data-testid="reference-video-file-input"
                    disabled={isLoading}
                  />
                </label>
              )}
            </div>

            {error && (
              <p className="text-sm text-pink-400" data-testid="reference-input-error">
                {error}
              </p>
            )}
            <button
              type="submit"
              className="glass-button w-full bg-neonBlue/20 py-3 text-base"
              disabled={isLoading}
            >
              {isLoading ? "Analysing reference..." : "Create & Analyse Reference"}
            </button>
          </form>
        </div>

        <MemoryPanel
          memoryContext={displayMemory.memory_context}
          memoryUpdates={displayMemory.memory_updates}
        />
      </div>
    </main>
  );
}
