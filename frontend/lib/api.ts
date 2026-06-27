import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

export type ProjectBlackboard = Record<string, unknown>;

export type ProjectSummary = {
  project_id: string;
  title: string;
  stage: string;
  user_id: string;
  created_at: string;
  updated_at: string;
};

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

export async function createProject(title: string, userId = "default-user") {
  const { data } = await api.post<ProjectBlackboard>("/api/projects", { title, user_id: userId });
  return data;
}

export async function getProject(projectId: string) {
  const { data } = await api.get<ProjectBlackboard>(`/api/projects/${projectId}`);
  return data;
}

export async function listProjects(userId?: string) {
  const { data } = await api.get<ProjectSummary[]>("/api/projects", {
    params: userId ? { user_id: userId } : undefined,
  });
  return data;
}

export async function deleteProject(projectId: string) {
  const { data } = await api.delete<{ project_id: string; deleted: boolean }>(
    `/api/projects/${projectId}`,
  );
  return data;
}

export async function uploadReference(projectId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/api/projects/${projectId}/upload-reference`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function setReferenceVideoUrl(projectId: string, videoUrl: string) {
  const { data } = await api.post(`/api/projects/${projectId}/reference-url`, {
    video_url: videoUrl,
  });
  return data;
}

export async function analyseReference(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/analyse-reference`);
  return data;
}

export async function setTopic(projectId: string, topic: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/topic`, { topic });
  return data;
}

export async function researchTopic(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/research`);
  return data;
}

export async function discoverCandidates(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/candidates/discover`);
  return data;
}

export type CandidateReviewStatus = {
  review_active: boolean;
  total_slots: number;
  approved_count: number;
  pending_count: number;
  exhausted_count: number;
  current_slot_rank?: number | null;
  current_status?: string | null;
  current_candidate?: Record<string, unknown> | null;
  message?: string;
};

export async function startCandidateReview(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/candidates/review/start`);
  return data;
}

export async function skipCandidateReviewSlot(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(
    `/api/projects/${projectId}/candidates/review/skip`,
  );
  return data;
}

export async function getCandidateReviewStatus(projectId: string) {
  const { data } = await api.get<CandidateReviewStatus>(
    `/api/projects/${projectId}/candidates/review/status`,
  );
  return data;
}

export async function selectRanking(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/ranking/select`);
  return data;
}

export async function approveCandidate(projectId: string, candidateId: string) {
  const { data } = await api.post<ProjectBlackboard>(
    `/api/projects/${projectId}/candidates/${candidateId}/approve`,
    {},
  );
  return data;
}

export async function rejectCandidate(projectId: string, candidateId: string) {
  const { data } = await api.post<ProjectBlackboard>(
    `/api/projects/${projectId}/candidates/${candidateId}/reject`,
    {},
  );
  return data;
}

export async function createEditPlan(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/edit-plan`);
  return data;
}

export async function approveEditPlan(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/edit-plan/approve`);
  return data;
}

export async function renderVideo(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/render`);
  return data;
}

export async function submitTextFeedback(projectId: string, feedbackText: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/feedback/text`, {
    feedback_text: feedbackText,
  });
  return data;
}

export async function regenerate(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/regenerate`);
  return data;
}

export async function finalApprove(projectId: string) {
  const { data } = await api.post<ProjectBlackboard>(`/api/projects/${projectId}/final-approve`);
  return data;
}

export async function getComparison(projectId: string) {
  const { data } = await api.get(`/api/projects/${projectId}/comparison`);
  return data;
}

export async function getTraces(projectId: string) {
  const { data } = await api.get(`/api/projects/${projectId}/traces`);
  return data;
}

export async function getDownloadEvents(projectId: string) {
  const { data } = await api.get(`/api/projects/${projectId}/downloads`);
  return data;
}

export async function getMemory(projectId: string) {
  const { data } = await api.get(`/api/projects/${projectId}/memory`);
  return data;
}

export async function getIntegrationStatus() {
  const { data } = await api.get("/api/health");
  return data;
}

export function mediaUrl(path: string | undefined | null): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${API_BASE}/${path.replace(/^\.?\//, "")}`;
}
