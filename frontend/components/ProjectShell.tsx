"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { DeleteProjectButton } from "@/components/DeleteProjectButton";
import { getProject } from "@/lib/api";

const STEPS = [
  { slug: "blueprint", label: "Blueprint" },
  { slug: "candidates", label: "Candidates" },
  { slug: "studio", label: "Studio" },
  { slug: "review", label: "Review" },
  { slug: "comparison", label: "Comparison" },
];

type ProjectShellProps = {
  children: ReactNode;
  active: string;
};

export function ProjectShell({ children, active }: ProjectShellProps) {
  const params = useParams();
  const router = useRouter();
  const projectId = String(params.id);
  const [projectTitle, setProjectTitle] = useState<string | null>(null);

  useEffect(() => {
    getProject(projectId)
      .then((project) => {
        if (typeof project.title === "string") {
          setProjectTitle(project.title);
        }
      })
      .catch(() => {
        setProjectTitle(null);
      });
  }, [projectId]);

  const handleProjectDeleted = () => {
    router.push("/");
  };

  return (
    <div className="min-h-screen">
      <header className="border-b border-white/10 bg-black/20 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="font-semibold text-neonBlue">
              EditDNA Rank Studio
            </Link>
            {projectTitle && (
              <span className="hidden text-sm text-slate-400 sm:inline" data-testid="project-shell-title">
                {projectTitle}
              </span>
            )}
          </div>
          <nav className="flex flex-wrap items-center gap-2">
            {STEPS.map((step) => (
              <Link
                key={step.slug}
                href={`/project/${projectId}/${step.slug}`}
                className={`rounded-lg px-3 py-1 text-sm ${
                  active === step.slug ? "bg-neonBlue/20 text-neonBlue" : "text-slate-400 hover:text-white"
                }`}
              >
                {step.label}
              </Link>
            ))}
            <DeleteProjectButton
              projectId={projectId}
              projectTitle={projectTitle || undefined}
              onDeleted={handleProjectDeleted}
              compact
            />
          </nav>
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-6 py-6">{children}</div>
    </div>
  );
}
