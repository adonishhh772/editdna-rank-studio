export type IntegrationHealthItem = {
  id: string;
  label: string;
  configured: boolean;
  reachable: boolean | null;
  status: string;
  message?: string | null;
  optional_in_demo?: boolean;
};

export type IntegrationHealthResponse = {
  status: string;
  missing_keys: string[];
  allow_demo_fallback: boolean;
  demo_mode?: string | null;
  gemini: boolean;
  tavily: boolean;
  slng: boolean;
  mubit: boolean;
  integrations: IntegrationHealthItem[];
};

export function resolveIntegrationStatusTone(item: IntegrationHealthItem): string {
  if (item.status === "ok" && item.reachable !== false) {
    return "text-neonGreen";
  }
  if (item.status === "ci_only" && item.configured) {
    return "text-neonGreen";
  }
  if (item.status === "skipped_demo" || item.optional_in_demo) {
    return "text-slate-400";
  }
  if (item.status === "missing_key") {
    return "text-amber-400";
  }
  return "text-pink-400";
}

export function resolveIntegrationStatusLabel(item: IntegrationHealthItem): string {
  if (item.status === "ok" && item.reachable === true) {
    return "Connected";
  }
  if (item.status === "ok" && item.reachable === null) {
    return "Configured";
  }
  if (item.status === "ci_only") {
    return item.configured ? "CI ready" : "CI needs secret";
  }
  if (item.status === "missing_key") {
    return "Missing key";
  }
  return "Error";
}
