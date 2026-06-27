export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export function resolveUploadMediaUrl(localFilePath: string | undefined): string | null {
  if (!localFilePath) {
    return null;
  }
  const uploadsIndex = localFilePath.indexOf("/uploads/");
  if (uploadsIndex >= 0) {
    return `${API_BASE}${localFilePath.slice(uploadsIndex)}`;
  }
  return null;
}

export function resolveReferenceMediaUrl(
  projectId: string,
  referenceVideoPath: string | undefined | null,
  referenceVideoUrl: string | undefined | null,
): string | null {
  const localUrl = resolveUploadMediaUrl(referenceVideoPath ?? undefined);
  if (localUrl) {
    return localUrl;
  }
  if (referenceVideoPath || referenceVideoUrl) {
    return `${API_BASE}/api/projects/${projectId}/media/reference`;
  }
  return null;
}

export function resolveOutputMediaUrl(projectId: string, outputVideoPath: string | undefined | null): string | null {
  const localUrl = resolveUploadMediaUrl(outputVideoPath ?? undefined);
  if (localUrl) {
    return localUrl;
  }
  if (outputVideoPath) {
    return `${API_BASE}/api/projects/${projectId}/media/output`;
  }
  return null;
}
