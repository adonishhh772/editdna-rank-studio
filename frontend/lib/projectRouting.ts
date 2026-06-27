import type { ProjectBlackboard } from "@/lib/api";

function hasItems(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0;
}

export function resolveProjectRoute(project: ProjectBlackboard): string {
  const projectId = String(project.project_id);

  if (project.comparison_report || project.stage === "compare") {
    return `/project/${projectId}/comparison`;
  }

  if (project.output_video_path) {
    return `/project/${projectId}/review`;
  }

  if (project.edit_plan || project.stage === "create_edit_plan" || project.stage === "render") {
    return `/project/${projectId}/studio`;
  }

  if (
    hasItems(project.selected_candidates) ||
    project.stage === "select_ranking" ||
    project.stage === "discover_candidates"
  ) {
    return `/project/${projectId}/candidates`;
  }

  return `/project/${projectId}/blueprint`;
}
