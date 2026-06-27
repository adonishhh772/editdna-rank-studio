"use client";

import { ShieldCheck } from "lucide-react";
import {
  resolveIntegrationStatusLabel,
  resolveIntegrationStatusTone,
  type IntegrationHealthItem,
} from "@/lib/integrationHealth";

type IntegrationStatusPanelProps = {
  integrations: IntegrationHealthItem[];
  isLoading: boolean;
};

export function IntegrationStatusPanel({
  integrations,
  isLoading,
}: IntegrationStatusPanelProps) {
  if (isLoading) {
    return (
      <div className="mt-8 rounded-xl border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
        Checking integrations...
      </div>
    );
  }

  if (integrations.length === 0) {
    return null;
  }

  return (
    <div
      className="mt-8 rounded-xl border border-white/10 bg-black/20 p-4"
      data-testid="integration-status-panel"
    >
      <div className="mb-4 flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-neonBlue" />
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
          Integration Health
        </h2>
      </div>
      <ul className="grid gap-3 md:grid-cols-2">
        {integrations.map((item) => (
          <li
            key={item.id}
            className="rounded-lg border border-white/5 bg-white/5 p-3"
            data-testid={`integration-status-${item.id}`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-slate-100">{item.label}</span>
              <span className={`text-xs font-semibold uppercase tracking-wider ${resolveIntegrationStatusTone(item)}`}>
                {resolveIntegrationStatusLabel(item)}
              </span>
            </div>
            {item.message && <p className="mt-2 text-xs text-slate-400">{item.message}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
