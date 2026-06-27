"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { getApiErrorMessage, getProject } from "@/lib/api";
import { resolveProjectRoute } from "@/lib/projectRouting";

export default function ProjectResumePage() {
  const params = useParams();
  const router = useRouter();
  const projectId = String(params.id);

  useEffect(() => {
    const resumeProject = async () => {
      try {
        const project = await getProject(projectId);
        router.replace(resolveProjectRoute(project));
      } catch (resumeError) {
        router.replace(`/?error=${encodeURIComponent(getApiErrorMessage(resumeError, "Project not found"))}`);
      }
    };

    resumeProject();
  }, [projectId, router]);

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-6">
      <p className="text-slate-400" data-testid="project-resume-loading">
        Opening saved project...
      </p>
    </main>
  );
}
