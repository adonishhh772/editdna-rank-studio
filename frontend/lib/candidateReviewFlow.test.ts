import {
  isReviewSlotReady,
  shouldAutoContinueReview,
} from "@/lib/candidateReviewFlow";

describe("candidateReviewFlow", () => {
  it("continues review when slots remain but no clip is ready", () => {
    expect(
      shouldAutoContinueReview({
        review_active: true,
        total_slots: 5,
        approved_count: 1,
        pending_count: 4,
        exhausted_count: 0,
        current_status: "pending",
        current_candidate: null,
      }),
    ).toBe(true);
  });

  it("stops when a clip is awaiting approval", () => {
    expect(
      shouldAutoContinueReview({
        review_active: true,
        total_slots: 5,
        approved_count: 1,
        pending_count: 4,
        exhausted_count: 0,
        current_status: "awaiting_approval",
        current_candidate: { candidate_id: "cand_1" },
      }),
    ).toBe(false);
    expect(
      isReviewSlotReady({
        review_active: true,
        total_slots: 5,
        approved_count: 1,
        pending_count: 4,
        exhausted_count: 0,
        current_status: "awaiting_approval",
        current_candidate: { candidate_id: "cand_1" },
      }),
    ).toBe(true);
  });

  it("does not continue while a slot is preparing", () => {
    expect(
      shouldAutoContinueReview({
        review_active: true,
        total_slots: 5,
        approved_count: 1,
        pending_count: 4,
        exhausted_count: 0,
        current_status: "preparing",
        current_candidate: null,
      }),
    ).toBe(false);
  });
});
