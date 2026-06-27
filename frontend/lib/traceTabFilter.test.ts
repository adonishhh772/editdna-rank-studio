import {
  filterAgentMessagesForTab,
  filterDownloadEventsForTab,
  filterTracesForTab,
} from "@/lib/traceTabFilter";

describe("traceTabFilter", () => {
  const traces = [
    { agent_id: "reference_video_probe" },
    { agent_id: "tavily_research" },
    { agent_id: "platform_video_search" },
    { agent_id: "moe_edit_swarm" },
    { agent_id: "rank_clip_render" },
    { agent_id: "comparison_agent" },
  ];

  it("shows only blueprint-related traces on the blueprint tab", () => {
    const filtered = filterTracesForTab(traces, "blueprint");
    expect(filtered.map((trace) => trace.agent_id)).toEqual([
      "reference_video_probe",
      "tavily_research",
    ]);
  });

  it("shows only candidate traces on the candidates tab", () => {
    const filtered = filterTracesForTab(traces, "candidates");
    expect(filtered.map((trace) => trace.agent_id)).toEqual(["platform_video_search"]);
  });

  it("shows only render traces on the review tab", () => {
    const filtered = filterTracesForTab(traces, "review");
    expect(filtered.map((trace) => trace.agent_id)).toEqual(["rank_clip_render"]);
  });

  it("filters download events to candidate stages only on candidates tab", () => {
    const events = [
      { stage: "download_success" },
      { stage: "stitch" },
    ];
    expect(filterDownloadEventsForTab(events, "candidates")).toHaveLength(1);
    expect(filterDownloadEventsForTab(events, "studio")).toHaveLength(0);
  });

  it("shows expert messages only on the studio tab", () => {
    const messages = [{ from_agent_id: "story_expert" }];
    expect(filterAgentMessagesForTab(messages, "studio")).toHaveLength(1);
    expect(filterAgentMessagesForTab(messages, "review")).toHaveLength(0);
  });
});
