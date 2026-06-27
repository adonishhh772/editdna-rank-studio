"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FolderOpen } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { DeleteProjectButton } from "@/components/DeleteProjectButton";
import { getProjectStageLabel } from "@/lib/constants/projectStages";
import { getApiErrorMessage, getProject, listProjects, type ProjectSummary } from "@/lib/api";
import { resolveProjectRoute } from "@/lib/projectRouting";

function formatProjectDate(value: string): string {
  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }
  return parsedDate.toLocaleString();
}

export function SavedProjectsPanel() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadProjects = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const projectList = await listProjects();
        setProjects(projectList);
      } catch (loadError) {
        setError(getApiErrorMessage(loadError, "Failed to load saved projects"));
      } finally {
        setIsLoading(false);
      }
    };

    loadProjects();
  }, []);

  const handleProjectDeleted = useCallback((projectId: string) => {
    setProjects((currentProjects) => currentProjects.filter((project) => project.project_id !== projectId));
  }, []);

  const handleContinueProject = async (projectId: string) => {
    setError(null);
    try {
      const project = await getProject(projectId);
      router.push(resolveProjectRoute(project));
    } catch (continueError) {
      setError(getApiErrorMessage(continueError, "Failed to open project"));
    }
  };

  return (
    <section className="glass-card mt-10" data-testid="saved-projects-panel">
      <div className="mb-6 flex items-center gap-3">
        <FolderOpen className="h-5 w-5 text-neonPurple" />
        <h2 className="text-xl font-semibold">Saved Projects</h2>
      </div>

      {isLoading && <p className="text-sm text-slate-400">Loading saved projects...</p>}
      {error && (
        <p className="text-sm text-pink-400" data-testid="saved-projects-error">
          {error}
        </p>
      )}

      {!isLoading && !error && projects.length === 0 && (
        <p className="text-sm text-slate-400">No saved projects yet. Start a new project to create one.</p>
      )}

      {!isLoading && projects.length > 0 && (
        <p className="mb-4 text-xs text-slate-500">
          Each project shows its current stage. Open a project to see every agent step in Live Activity.
        </p>
      )}

      {!isLoading && projects.length > 0 && (
        <div className="space-y-3">
          {projects.map((project) => (
            <article
              key={project.project_id}
              className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-white/5 bg-black/20 p-4"
              data-testid={`saved-project-${project.project_id}`}
            >
              <div>
                <h3 className="font-semibold text-slate-100">{project.title}</h3>
                <p className="mt-1 text-xs text-slate-500">
                  Updated {formatProjectDate(project.updated_at)}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-neonBlue/30 bg-neonBlue/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-neonBlue">
                  {getProjectStageLabel(project.stage)}
                </span>
                <button
                  type="button"
                  className="glass-button bg-neonPurple/20"
                  onClick={() => handleContinueProject(project.project_id)}
                  data-testid={`continue-project-${project.project_id}`}
                >
                  Continue
                </button>
                <Link
                  href={`/project/${project.project_id}`}
                  className="glass-button text-sm text-slate-300"
                >
                  Open
                </Link>
                <DeleteProjectButton
                  projectId={project.project_id}
                  projectTitle={project.title}
                  onDeleted={() => handleProjectDeleted(project.project_id)}
                  compact
                />
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
