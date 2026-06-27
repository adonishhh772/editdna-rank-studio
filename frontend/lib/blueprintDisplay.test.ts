import {
  buildBlueprintOverviewMetrics,
  buildBlueprintPatternMetrics,
  buildBlueprintSections,
  buildBlueprintStyleSections,
  flattenStyleDict,
  formatConfidencePercent,
  formatSnakeCaseLabel,
  formatTimeRange,
  formatTimestamp,
  resolveConfidenceAccent,
} from "@/lib/blueprintDisplay";

describe("blueprintDisplay", () => {
  it("formats snake_case labels into readable text", () => {
    expect(formatSnakeCaseLabel("text_based_instruction_and_visual_teaser")).toBe(
      "Text Based Instruction And Visual Teaser",
    );
    expect(formatSnakeCaseLabel("")).toBe("—");
  });

  it("formats timestamps and time ranges", () => {
    expect(formatTimestamp(65)).toBe("01:05");
    expect(formatTimeRange(3.2, 12.8)).toBe("00:03 – 00:12");
  });

  it("formats confidence values", () => {
    expect(formatConfidencePercent(0.847)).toBe("85%");
    expect(resolveConfidenceAccent(0.9)).toBe("green");
    expect(resolveConfidenceAccent(0.7)).toBe("orange");
    expect(resolveConfidenceAccent(0.4)).toBe("pink");
  });

  it("builds overview metrics from blueprint data", () => {
    const metrics = buildBlueprintOverviewMetrics({
      duration_sec: 24.5,
      aspect_ratio: "9:16",
      ranking_count: 5,
      ranking_order: "5_to_1",
      hook_duration_sec: 2.5,
      average_item_duration_sec: 3.8,
      outro_duration_sec: 1.2,
      confidence: 0.82,
      final_rank_drama_level: "high",
    });

    expect(metrics).toHaveLength(9);
    expect(metrics[0]?.value).toBe("24.5s");
    expect(metrics[3]?.value).toBe("#5 → #1");
    expect(metrics[7]?.value).toBe("82%");
    expect(metrics[7]?.accent).toBe("green");
  });

  it("builds readable pattern metrics", () => {
    const metrics = buildBlueprintPatternMetrics({
      hook_style: "text_based_instruction_and_visual_teaser",
      rank_reveal_style: "sequential_text_overlay_with_sound_effect_and_corresponding_video_segment",
    });

    expect(metrics[0]?.value).toBe("Text Based Instruction And Visual Teaser");
    expect(metrics[1]?.value).toBe(
      "Sequential Text Overlay With Sound Effect And Corresponding Video Segment",
    );
  });

  it("flattens nested style dictionaries", () => {
    const entries = flattenStyleDict({
      prominence: "high",
      typography: { case: "upper", weight: "bold" },
      effects: ["glow", "shadow"],
    });

    expect(entries).toEqual([
      { key: "Prominence", value: "high" },
      { key: "Typography.Case", value: "upper" },
      { key: "Typography.Weight", value: "bold" },
      { key: "Effects", value: "glow, shadow" },
    ]);
  });

  it("builds section timeline entries", () => {
    const sections = buildBlueprintSections({
      section_order: [
        {
          name: "Hook",
          rank_number: null,
          start_sec: 0,
          end_sec: 2.5,
          purpose: "Set up the ranking premise",
          visual_notes: "Fast cuts",
          audio_notes: "Whoosh sfx",
          text_notes: "Top 5 tools",
          motion_notes: "Zoom in",
        },
      ],
    });

    expect(sections).toHaveLength(1);
    expect(sections[0]?.name).toBe("Hook");
    expect(sections[0]?.timeRange).toBe("00:00 – 00:02");
    expect(sections[0]?.visualNotes).toBe("Fast cuts");
  });

  it("builds non-empty style sections only", () => {
    const styleSections = buildBlueprintStyleSections({
      caption_style: { prominence: "high" },
      text_overlay_style: {},
      audio_style: { mood: "energetic" },
    });

    expect(styleSections).toHaveLength(2);
    expect(styleSections[0]?.title).toBe("Captions");
    expect(styleSections[1]?.title).toBe("Audio");
  });
});
