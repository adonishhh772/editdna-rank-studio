export type CandidateReviewStatus = {
  review_active: boolean;
  total_slots: number;
  approved_count: number;
  pending_count: number;
  exhausted_count: number;
  current_slot_rank?: number | null;
  current_status?: string | null;
  current_candidate?: unknown | null;
  message?: string;
};

export const REVIEW_STATUS_PREPARING = "preparing";
export const REVIEW_STATUS_AWAITING_APPROVAL = "awaiting_approval";

export const MAX_AUTO_CONTINUE_ATTEMPTS = 5;

export function shouldAutoContinueReview(status: CandidateReviewStatus): boolean {
  return (
    status.review_active &&
    status.pending_count > 0 &&
    !status.current_candidate &&
    status.current_status !== REVIEW_STATUS_PREPARING &&
    status.current_status !== REVIEW_STATUS_AWAITING_APPROVAL
  );
}

export function isReviewSlotReady(status: CandidateReviewStatus): boolean {
  return (
    status.current_status === REVIEW_STATUS_AWAITING_APPROVAL &&
    Boolean(status.current_candidate)
  );
}

export async function continueReviewUntilReady(
  projectId: string,
  runStream: (path: string) => Promise<Record<string, unknown> | null>,
  fetchStatus: () => Promise<CandidateReviewStatus>,
  maxAttempts: number = MAX_AUTO_CONTINUE_ATTEMPTS,
): Promise<CandidateReviewStatus> {
  let status = await fetchStatus();
  let attempts = 0;

  while (shouldAutoContinueReview(status) && attempts < maxAttempts) {
    await runStream(`/api/projects/${projectId}/candidates/review/start`);
    status = await fetchStatus();
    attempts += 1;

    if (isReviewSlotReady(status)) {
      break;
    }
  }

  return status;
}
