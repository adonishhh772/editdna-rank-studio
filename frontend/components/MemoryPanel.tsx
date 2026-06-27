"use client";

import { Brain } from "lucide-react";
import { AccordionSection } from "@/components/AccordionSection";

type MemoryPanelProps = {
  memoryContext: Record<string, unknown>;
  memoryUpdates: Array<Record<string, unknown>>;
};

function collectMemoryItems(
  memoryUpdates: Array<Record<string, unknown>>,
  field: "short_term_updates" | "episodic_updates" | "long_term_updates",
): Array<Record<string, unknown>> {
  const items: Array<Record<string, unknown>> = [];
  const seen = new Set<string>();

  for (const update of memoryUpdates) {
    const updates = (update[field] as Array<Record<string, unknown>>) || [];
    for (const item of updates) {
      const content = String(item.content || "");
      if (!content || seen.has(content)) {
        continue;
      }
      seen.add(content);
      items.push(item);
    }
  }

  return items;
}

export function MemoryPanel({ memoryContext, memoryUpdates }: MemoryPanelProps) {
  const shortTerm = collectMemoryItems(memoryUpdates, "short_term_updates");
  const episodic = collectMemoryItems(memoryUpdates, "episodic_updates");
  const longTerm = collectMemoryItems(memoryUpdates, "long_term_updates");
  const finalAnswer = String(memoryContext.final_answer || "");

  return (
    <aside className="glass-card flex max-h-[calc(100vh-8rem)] flex-col" data-testid="memory-panel">
      <div className="mb-4 flex items-center gap-2">
        <Brain className="h-5 w-5 text-neonBlue" />
        <h2 className="text-lg font-semibold tracking-wide">EditDNA Memory</h2>
      </div>

      <div className="space-y-3 overflow-y-auto pr-1">
        <AccordionSection
          title="Short-term"
          defaultOpen
          badge={String(shortTerm.length + (finalAnswer ? 1 : 0))}
          testId="memory-short-term"
          contentClassName="max-h-36 overflow-y-auto"
        >
          <ul className="space-y-1 text-sm text-slate-300">
            {finalAnswer && <li>- {finalAnswer}</li>}
            {shortTerm.map((item, index) => (
              <li key={`st-${index}`}>- {String(item.content)}</li>
            ))}
            {shortTerm.length === 0 && !finalAnswer && (
              <li className="text-slate-500">No short-term memory yet.</li>
            )}
          </ul>
        </AccordionSection>

        <AccordionSection
          title="Episodic"
          badge={String(episodic.length)}
          testId="memory-episodic"
          contentClassName="max-h-36 overflow-y-auto"
        >
          <ul className="space-y-1 text-sm text-slate-300">
            {episodic.map((item, index) => (
              <li key={`ep-${index}`}>- {String(item.content)}</li>
            ))}
            {episodic.length === 0 && <li className="text-slate-500">No episodic memory yet.</li>}
          </ul>
        </AccordionSection>

        <AccordionSection
          title="Long-term"
          badge={String(longTerm.length)}
          testId="memory-long-term"
          contentClassName="max-h-36 overflow-y-auto"
        >
          <ul className="space-y-1 text-sm text-slate-300">
            {longTerm.map((item, index) => (
              <li key={`lt-${index}`}>- {String(item.content)}</li>
            ))}
            {longTerm.length === 0 && <li className="text-slate-500">No long-term memory written yet.</li>}
          </ul>
        </AccordionSection>
      </div>
    </aside>
  );
}
