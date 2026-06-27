import { resolveDisplayMemory } from "@/lib/memoryDisplay";

describe("resolveDisplayMemory", () => {
  it("prefers streamed memory updates when present", () => {
    const result = resolveDisplayMemory(
      {
        memory_context: { persisted: true },
        memory_updates: [{ summary: "persisted" }],
      },
      {
        memory_context: { streamed: true },
        memory_updates: [{ summary: "streamed" }],
      },
    );

    expect(result.memory_context).toEqual({ streamed: true });
    expect(result.memory_updates).toEqual([{ summary: "streamed" }]);
  });

  it("falls back to persisted memory when stream is empty", () => {
    const persisted = {
      memory_context: { reference_blueprint_memory: { summary: "saved" } },
      memory_updates: [{ summary: "saved" }],
    };

    const result = resolveDisplayMemory(persisted, {
      memory_context: {},
      memory_updates: [],
    });

    expect(result).toEqual(persisted);
  });
});
