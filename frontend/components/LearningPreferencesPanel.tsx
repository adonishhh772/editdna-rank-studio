"use client";

import { Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";
import { AccordionSection } from "@/components/AccordionSection";

type PreferenceExample = {
  concept?: string;
  duration_sec?: number;
  orientation?: string;
  aspect_ratio_hint?: string;
  source_url?: string;
};

type VideoPreferencesSummary = {
  notes?: string[];
  approved_examples?: PreferenceExample[];
  rejected_examples?: PreferenceExample[];
  blocked_orientations?: string[];
  max_duration_sec?: number | null;
  preferred_duration_sec?: number | null;
  has_learning?: boolean;
};

type LearningPreferencesPanelProps = {
  memoryContext: Record<string, unknown>;
};

function readVideoPreferences(memoryContext: Record<string, unknown>): VideoPreferencesSummary {
  const raw = memoryContext.video_preferences;
  if (!raw || typeof raw !== "object") {
    return { has_learning: false };
  }
  const preferences = raw as VideoPreferencesSummary;
  return {
    notes: Array.isArray(preferences.notes) ? preferences.notes : [],
    approved_examples: Array.isArray(preferences.approved_examples)
      ? preferences.approved_examples
      : [],
    rejected_examples: Array.isArray(preferences.rejected_examples)
      ? preferences.rejected_examples
      : [],
    blocked_orientations: Array.isArray(preferences.blocked_orientations)
      ? preferences.blocked_orientations
      : [],
    max_duration_sec: preferences.max_duration_sec ?? null,
    preferred_duration_sec: preferences.preferred_duration_sec ?? null,
    has_learning: Boolean(
      (preferences.notes && preferences.notes.length > 0)
      || (preferences.approved_examples && preferences.approved_examples.length > 0)
      || (preferences.rejected_examples && preferences.rejected_examples.length > 0),
    ),
  };
}

function formatExample(example: PreferenceExample): string {
  const concept = example.concept || "clip";
  const duration = example.duration_sec;
  const orientation = example.orientation || "unknown";
  if (typeof duration === "number") {
    return `${concept} · ${duration.toFixed(0)}s · ${orientation}`;
  }
  return `${concept} · ${orientation}`;
}

export function LearningPreferencesPanel({ memoryContext }: LearningPreferencesPanelProps) {
  const preferences = readVideoPreferences(memoryContext);

  return (
    <aside className="glass-card flex max-h-[calc(100vh-8rem)] flex-col" data-testid="learning-preferences-panel">
      <div className="mb-4 flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-neonGreen" />
        <h2 className="text-lg font-semibold tracking-wide">Learning</h2>
      </div>

      {!preferences.has_learning && (
        <p className="text-sm text-slate-400">
          Approve or reject candidates to teach the system your preferred clip length, orientation, and style.
        </p>
      )}

      {preferences.has_learning && (
        <div className="space-y-3 overflow-y-auto pr-1">
          {(preferences.preferred_duration_sec || preferences.max_duration_sec) && (
            <AccordionSection
              title="Duration rules"
              defaultOpen
              testId="learning-duration-rules"
              contentClassName="max-h-28 overflow-y-auto"
            >
              <div className="rounded-lg border border-neonGreen/20 bg-neonGreen/5 p-3">
                {preferences.preferred_duration_sec && (
                  <p className="text-sm text-slate-300">
                    Preferred: ~{preferences.preferred_duration_sec.toFixed(0)}s sources
                  </p>
                )}
                {preferences.max_duration_sec && (
                  <p className="text-sm text-slate-400">
                    Avoid longer than ~{preferences.max_duration_sec.toFixed(0)}s
                  </p>
                )}
              </div>
            </AccordionSection>
          )}

          {preferences.blocked_orientations && preferences.blocked_orientations.length > 0 && (
            <AccordionSection
              title="Blocked orientations"
              testId="learning-blocked-orientations"
              contentClassName="max-h-24 overflow-y-auto"
            >
              <p className="text-sm text-pink-400">{preferences.blocked_orientations.join(", ")}</p>
            </AccordionSection>
          )}

          {preferences.notes && preferences.notes.length > 0 && (
            <AccordionSection
              title="Recent decisions"
              defaultOpen
              badge={String(preferences.notes.length)}
              testId="learning-recent-decisions"
              contentClassName="max-h-36 overflow-y-auto"
            >
              <ul className="space-y-1 text-sm text-slate-300">
                {preferences.notes.map((note, index) => (
                  <li key={`learning-note-${index}`}>- {note}</li>
                ))}
              </ul>
            </AccordionSection>
          )}

          {preferences.approved_examples && preferences.approved_examples.length > 0 && (
            <AccordionSection
              title="Approved profile"
              icon={<ThumbsUp className="h-3 w-3 text-neonGreen" />}
              badge={String(preferences.approved_examples.length)}
              testId="learning-approved-profile"
              contentClassName="max-h-36 overflow-y-auto"
            >
              <ul className="space-y-1 text-sm text-slate-300">
                {preferences.approved_examples.map((example, index) => (
                  <li key={`approved-${index}`}>+ {formatExample(example)}</li>
                ))}
              </ul>
            </AccordionSection>
          )}

          {preferences.rejected_examples && preferences.rejected_examples.length > 0 && (
            <AccordionSection
              title="Avoid similar to"
              icon={<ThumbsDown className="h-3 w-3 text-pink-400" />}
              badge={String(preferences.rejected_examples.length)}
              testId="learning-rejected-profile"
              contentClassName="max-h-36 overflow-y-auto"
            >
              <ul className="space-y-1 text-sm text-slate-300">
                {preferences.rejected_examples.map((example, index) => (
                  <li key={`rejected-${index}`}>- {formatExample(example)}</li>
                ))}
              </ul>
            </AccordionSection>
          )}
        </div>
      )}
    </aside>
  );
}
