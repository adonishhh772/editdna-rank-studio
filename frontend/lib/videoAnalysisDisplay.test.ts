import { describe, expect, it } from "vitest";
import {
  buildEditVideoInsightsFromPlan,
  buildEditVideoInsightsFromSections,
} from "./videoAnalysisDisplay";

describe("buildEditVideoInsightsFromPlan", () => {
  it("maps saved video insights from edit plan", () => {
    const insights = buildEditVideoInsightsFromPlan({
      video_insights: {
        reference: {
          hook_style: "question",
          rank_reveal_style: "countdown",
          ranking_count: 5,
          average_item_duration_sec: 4.2,
          final_rank_drama_level: "high",
          aspect_ratio: "9:16",
          duration_sec: 30,
        },
        candidates: [
          {
            candidate_id: "cand-1",
            rank: 1,
            title: "Clip A",
            concept: "Best pick",
            reason: "Strong fit",
            highlight_reason: "Peak motion window",
            clip_start_sec: 1,
            clip_end_sec: 5,
            analysis_source: "gemini",
            scores: {
              topic_match: 0.8,
              overall: 0.75,
            },
          },
        ],
      },
    });

    expect(insights.reference?.hookStyle).toBe("question");
    expect(insights.candidates).toHaveLength(1);
    expect(insights.candidates[0].highlightReason).toBe("Peak motion window");
    expect(insights.candidates[0].scores).toHaveLength(2);
  });
});

describe("buildEditVideoInsightsFromSections", () => {
  it("falls back to section analysis scores when video_insights is empty", () => {
    const insights = buildEditVideoInsightsFromSections({
      sections: [
        {
          candidate_id: "cand-2",
          rank: 2,
          title: "Clip B",
          label_text: "Runner up",
          reason: "Good pacing",
          highlight_reason: "Stable middle segment",
          clip_start_sec: 2,
          clip_end_sec: 6,
          analysis_scores: {
            motion_energy: 0.66,
            overall: 0.7,
          },
        },
      ],
    });

    expect(insights.candidates).toHaveLength(1);
    expect(insights.candidates[0].clipRange).toBe("2.0s – 6.0s");
    expect(insights.candidates[0].scores.some((score) => score.key === "motion_energy")).toBe(true);
  });
});
