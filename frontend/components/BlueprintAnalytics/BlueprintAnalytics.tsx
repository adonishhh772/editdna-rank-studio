"use client";

import { Clock3, Film, Layers3, Sparkles } from "lucide-react";
import { AccordionSection } from "@/components/AccordionSection";
import {
  buildBlueprintOverviewMetrics,
  buildBlueprintPatternMetrics,
  buildBlueprintSections,
  buildBlueprintStyleSections,
  type BlueprintMetric,
} from "@/lib/blueprintDisplay";

type BlueprintAnalyticsProps = {
  blueprint: Record<string, unknown>;
};

const ACCENT_TEXT_CLASSES: Record<NonNullable<BlueprintMetric["accent"]>, string> = {
  blue: "text-neonBlue",
  purple: "text-neonPurple",
  green: "text-neonGreen",
  teal: "text-teal-400",
  orange: "text-amber-400",
  pink: "text-pink-400",
};

export function BlueprintAnalytics({ blueprint }: BlueprintAnalyticsProps) {
  const overviewMetrics = buildBlueprintOverviewMetrics(blueprint);
  const patternMetrics = buildBlueprintPatternMetrics(blueprint);
  const sections = buildBlueprintSections(blueprint);
  const styleSections = buildBlueprintStyleSections(blueprint);

  return (
    <div className="space-y-6" data-testid="blueprint-analytics">
      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
          <Sparkles className="h-4 w-4 text-neonBlue" />
          Overview
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {overviewMetrics.map((metric) => (
            <MetricCard key={metric.label} metric={metric} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
          <Film className="h-4 w-4 text-neonPurple" />
          Editing Patterns
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          {patternMetrics.map((metric) => (
            <MetricCard key={metric.label} metric={metric} multiline />
          ))}
        </div>
      </section>

      {sections.length > 0 && (
        <section>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
            <Clock3 className="h-4 w-4 text-teal-400" />
            Section Timeline
            <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-slate-400">
              {sections.length}
            </span>
          </h2>
          <div className="space-y-3">
            {sections.map((section) => (
              <div
                key={section.id}
                className="rounded-xl border border-white/5 bg-black/20 p-4"
                data-testid={`blueprint-section-${section.id}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {section.rankLabel && (
                      <span className="rounded-full bg-neonPurple/20 px-2 py-0.5 text-xs font-bold text-neonPurple">
                        {section.rankLabel}
                      </span>
                    )}
                    <span className="font-semibold">{section.name}</span>
                  </div>
                  <span className="text-xs font-medium text-teal-400">{section.timeRange}</span>
                </div>
                {section.purpose && (
                  <p className="mt-2 text-sm text-slate-300">{section.purpose}</p>
                )}
                <SectionNotes section={section} />
              </div>
            ))}
          </div>
        </section>
      )}

      {styleSections.length > 0 && (
        <section>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
            <Layers3 className="h-4 w-4 text-amber-400" />
            Style Breakdown
          </h2>
          <div className="space-y-2">
            {styleSections.map((styleSection) => (
              <AccordionSection
                key={styleSection.id}
                title={styleSection.title}
                badge={String(styleSection.entries.length)}
                testId={`blueprint-style-${styleSection.id}`}
                contentClassName="max-h-56 overflow-y-auto pr-1"
              >
                <dl className="space-y-2">
                  {styleSection.entries.map((entry) => (
                    <div key={`${styleSection.id}-${entry.key}`} className="grid gap-1 sm:grid-cols-[140px_1fr]">
                      <dt className="text-xs uppercase tracking-wider text-slate-500">{entry.key}</dt>
                      <dd className="text-sm text-slate-200">{entry.value}</dd>
                    </div>
                  ))}
                </dl>
              </AccordionSection>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function MetricCard({
  metric,
  multiline = false,
}: {
  metric: BlueprintMetric;
  multiline?: boolean;
}) {
  const accentClass = metric.accent ? ACCENT_TEXT_CLASSES[metric.accent] : "text-slate-100";

  return (
    <div className="min-w-0 overflow-hidden rounded-xl border border-white/5 bg-black/20 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{metric.label}</p>
      <p
        className={`mt-1 text-lg font-semibold ${accentClass} ${
          multiline ? "whitespace-normal break-words leading-snug" : "truncate"
        }`}
        title={metric.value}
      >
        {metric.value}
      </p>
    </div>
  );
}

function SectionNotes({
  section,
}: {
  section: ReturnType<typeof buildBlueprintSections>[number];
}) {
  const noteEntries = [
    { label: "Visual", value: section.visualNotes },
    { label: "Audio", value: section.audioNotes },
    { label: "Text", value: section.textNotes },
    { label: "Motion", value: section.motionNotes },
  ].filter((entry) => entry.value.trim().length > 0);

  if (noteEntries.length === 0) {
    return null;
  }

  return (
    <dl className="mt-3 grid gap-2 sm:grid-cols-2">
      {noteEntries.map((entry) => (
        <div key={entry.label} className="rounded-lg bg-white/5 px-3 py-2">
          <dt className="text-[10px] uppercase tracking-wider text-slate-500">{entry.label}</dt>
          <dd className="mt-1 text-xs text-slate-400">{entry.value}</dd>
        </div>
      ))}
    </dl>
  );
}
