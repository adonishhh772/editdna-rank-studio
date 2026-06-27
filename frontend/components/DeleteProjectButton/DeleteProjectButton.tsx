"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteProject, getApiErrorMessage } from "@/lib/api";

const DELETE_CONFIRM_MESSAGE =
  "Delete this project permanently? This removes the blueprint, memory, candidates, and uploaded files.";

type DeleteProjectButtonProps = {
  projectId: string;
  projectTitle?: string;
  onDeleted: () => void;
  compact?: boolean;
};

export function DeleteProjectButton({
  projectId,
  projectTitle,
  onDeleted,
  compact = false,
}: DeleteProjectButtonProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDeleteClick = async () => {
    const label = projectTitle ? `"${projectTitle}"` : "this project";
    const confirmed = window.confirm(`${DELETE_CONFIRM_MESSAGE}\n\nProject: ${label}`);
    if (!confirmed) {
      return;
    }

    setIsDeleting(true);
    setError(null);

    try {
      await deleteProject(projectId);
      onDeleted();
    } catch (deleteError) {
      setError(getApiErrorMessage(deleteError, "Failed to delete project"));
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        className={`glass-button text-pink-400 hover:bg-pink-500/10 ${compact ? "px-3 py-1 text-sm" : ""}`}
        onClick={handleDeleteClick}
        disabled={isDeleting}
        data-testid={`delete-project-${projectId}`}
        aria-label={projectTitle ? `Delete ${projectTitle}` : "Delete project"}
      >
        <Trash2 className={`inline ${compact ? "mr-1 h-3 w-3" : "mr-2 h-4 w-4"}`} />
        {isDeleting ? "Deleting..." : "Delete"}
      </button>
      {error && (
        <p className="max-w-xs text-right text-xs text-pink-400" data-testid={`delete-project-error-${projectId}`}>
          {error}
        </p>
      )}
    </div>
  );
}
