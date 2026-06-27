export type BlueprintMetric = {
  label: string;
  value: string;
  accent?: "blue" | "purple" | "green" | "teal" | "orange" | "pink";
};

export type BlueprintStyleEntry = {
  key: string;
  value: string;
};

export type BlueprintSectionDisplay = {
  id: string;
  name: string;
  rankLabel: string | null;
  timeRange: string;
  purpose: string;
  visualNotes: string;
  audioNotes: string;
  textNotes: string;
  motionNotes: string;
};

const RANKING_ORDER_LABELS: Record<string, string> = {
  "5_to_1": "#5 → #1",
  "1_to_5": "#1 → #5",
  unknown: "Unknown",
};

const DRAMA_LEVEL_LABELS: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

const STYLE_SECTION_LABELS: Record<string, string> = {
  caption_style: "Captions",
  text_overlay_style: "Text Overlays",
  transition_style: "Transitions",
  audio_style: "Audio",
  motion_style: "Motion",
  pacing_style: "Pacing",
};

export function formatSnakeCaseLabel(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "—";
  }

  return trimmed
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function formatTimestamp(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainingSeconds = safeSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function formatTimeRange(startSec: number, endSec: number): string {
  return `${formatTimestamp(startSec)} – ${formatTimestamp(endSec)}`;
}

export function formatConfidencePercent(confidence: number): string {
  const clamped = Math.min(1, Math.max(0, confidence));
  return `${Math.round(clamped * 100)}%`;
}

export function resolveConfidenceAccent(confidence: number): BlueprintMetric["accent"] {
  if (confidence >= 0.8) {
    return "green";
  }
  if (confidence >= 0.6) {
    return "orange";
  }
  return "pink";
}

export function formatRankingOrder(value: string): string {
  return RANKING_ORDER_LABELS[value] ?? formatSnakeCaseLabel(value);
}

export function formatDramaLevel(value: string): string {
  return DRAMA_LEVEL_LABELS[value] ?? formatSnakeCaseLabel(value);
}

export function flattenStyleDict(style: Record<string, unknown>, prefix = ""): BlueprintStyleEntry[] {
  const entries: BlueprintStyleEntry[] = [];

  for (const [rawKey, rawValue] of Object.entries(style)) {
    const key = prefix ? `${prefix}.${rawKey}` : rawKey;

    if (rawValue === null || rawValue === undefined) {
      continue;
    }

    if (Array.isArray(rawValue)) {
      entries.push({
        key: formatSnakeCaseLabel(key),
        value: rawValue.map((item) => String(item)).join(", "),
      });
      continue;
    }

    if (typeof rawValue === "object") {
      entries.push(...flattenStyleDict(rawValue as Record<string, unknown>, key));
      continue;
    }

    entries.push({
      key: formatSnakeCaseLabel(key),
      value: String(rawValue),
    });
  }

  return entries;
}

export function buildBlueprintOverviewMetrics(blueprint: Record<string, unknown>): BlueprintMetric[] {
  const confidence = typeof blueprint.confidence === "number" ? blueprint.confidence : 0;

  return [
    {
      label: "Total duration",
      value: `${Number(blueprint.duration_sec ?? 0).toFixed(1)}s`,
      accent: "blue",
    },
    {
      label: "Aspect ratio",
      value: String(blueprint.aspect_ratio ?? "—"),
      accent: "purple",
    },
    {
      label: "Ranking count",
      value: String(blueprint.ranking_count ?? "—"),
      accent: "teal",
    },
    {
      label: "Ranking order",
      value: formatRankingOrder(String(blueprint.ranking_order ?? "unknown")),
      accent: "teal",
    },
    {
      label: "Hook length",
      value: `${Number(blueprint.hook_duration_sec ?? 0).toFixed(1)}s`,
      accent: "blue",
    },
    {
      label: "Avg item duration",
      value: `${Number(blueprint.average_item_duration_sec ?? 0).toFixed(1)}s`,
      accent: "blue",
    },
    {
      label: "Outro length",
      value: `${Number(blueprint.outro_duration_sec ?? 0).toFixed(1)}s`,
      accent: "blue",
    },
    {
      label: "Analysis confidence",
      value: formatConfidencePercent(confidence),
      accent: resolveConfidenceAccent(confidence),
    },
    {
      label: "#1 drama",
      value: formatDramaLevel(String(blueprint.final_rank_drama_level ?? "unknown")),
      accent: "orange",
    },
  ];
}

export function buildBlueprintPatternMetrics(blueprint: Record<string, unknown>): BlueprintMetric[] {
  return [
    {
      label: "Hook style",
      value: formatSnakeCaseLabel(String(blueprint.hook_style ?? "")),
      accent: "purple",
    },
    {
      label: "Rank reveal",
      value: formatSnakeCaseLabel(String(blueprint.rank_reveal_style ?? "")),
      accent: "purple",
    },
  ];
}

export function buildBlueprintSections(blueprint: Record<string, unknown>): BlueprintSectionDisplay[] {
  const sections = Array.isArray(blueprint.section_order)
    ? (blueprint.section_order as Array<Record<string, unknown>>)
    : [];

  return sections.map((section, index) => {
    const startSec = Number(section.start_sec ?? 0);
    const endSec = Number(section.end_sec ?? 0);
    const rankNumber = section.rank_number;

    return {
      id: `${String(section.name ?? "section")}-${index}`,
      name: String(section.name ?? `Section ${index + 1}`),
      rankLabel: typeof rankNumber === "number" ? `#${rankNumber}` : null,
      timeRange: formatTimeRange(startSec, endSec),
      purpose: String(section.purpose ?? ""),
      visualNotes: String(section.visual_notes ?? ""),
      audioNotes: String(section.audio_notes ?? ""),
      textNotes: String(section.text_notes ?? ""),
      motionNotes: String(section.motion_notes ?? ""),
    };
  });
}

export function buildBlueprintStyleSections(
  blueprint: Record<string, unknown>,
): Array<{ id: string; title: string; entries: BlueprintStyleEntry[] }> {
  return Object.entries(STYLE_SECTION_LABELS)
    .map(([fieldKey, title]) => {
      const rawStyle = blueprint[fieldKey];
      const styleDict =
        rawStyle && typeof rawStyle === "object" && !Array.isArray(rawStyle)
          ? (rawStyle as Record<string, unknown>)
          : {};

      return {
        id: fieldKey,
        title,
        entries: flattenStyleDict(styleDict),
      };
    })
    .filter((section) => section.entries.length > 0);
}
