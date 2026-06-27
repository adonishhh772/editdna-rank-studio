"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Clapperboard, Sparkles, Wand2 } from "lucide-react";
import { SavedProjectsPanel } from "@/components/SavedProjectsPanel";
import { getIntegrationStatus } from "@/lib/api";

export default function LandingPage() {
  const [missingKeys, setMissingKeys] = useState<string[]>([]);

  useEffect(() => {
    getIntegrationStatus()
      .then((status) => setMissingKeys(status.missing_keys || []))
      .catch(() => setMissingKeys(["API unreachable"]));
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-6 py-16">
      <div className="glass-card relative overflow-hidden">
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-neonPurple/20 blur-3xl" />
        <div className="absolute -bottom-10 -left-10 h-40 w-40 rounded-full bg-neonBlue/20 blur-3xl" />
        <div className="relative">
          <div className="mb-6 flex items-center gap-3 text-neonBlue">
            <Clapperboard className="h-8 w-8" />
            <span className="text-sm font-bold uppercase tracking-[0.3em]">EditDNA Rank Studio</span>
          </div>
          <h1 className="max-w-3xl text-5xl font-bold leading-tight">
            Upload one ranking video. Generate the next one in your style.
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-slate-300">
            The user is the creative director. Agents do the editing. Gemini extracts editing grammar,
            Tavily researches topics, SLNG handles audio intelligence, and Mubit remembers what you approve.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link href="/project/new" className="glass-button inline-flex items-center gap-2 bg-neonBlue/20">
              <Sparkles className="h-4 w-4" /> Start New Project
            </Link>
          </div>
          {missingKeys.length > 0 && (
            <div className="mt-8 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
              Missing API keys: {missingKeys.map((key) => `Missing ${key}`).join(", ")}
            </div>
          )}
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {[
              "Gemini video understanding",
              "Tavily topic research",
              "SLNG voice + audio",
              "Mubit durable memory",
              "Multi-agent blackboard swarm",
              "FFmpeg ranking render",
            ].map((item) => (
              <div key={item} className="rounded-xl border border-white/5 bg-black/20 p-4 text-sm text-slate-300">
                <Wand2 className="mb-2 h-4 w-4 text-neonPurple" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
      <SavedProjectsPanel />
    </main>
  );
}
