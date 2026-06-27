type MemoryPayload = {
  memory_context: Record<string, unknown>;
  memory_updates: Array<Record<string, unknown>>;
};

export function resolveDisplayMemory(
  persistedMemory: MemoryPayload,
  streamedMemory: MemoryPayload,
): MemoryPayload {
  const hasStreamedUpdates = streamedMemory.memory_updates.length > 0;
  const hasStreamedContext = Object.keys(streamedMemory.memory_context).length > 0;

  return {
    memory_context: hasStreamedContext ? streamedMemory.memory_context : persistedMemory.memory_context,
    memory_updates: hasStreamedUpdates ? streamedMemory.memory_updates : persistedMemory.memory_updates,
  };
}
