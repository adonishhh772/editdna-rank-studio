"use client";

type ScoreCardProps = {
  label: string;
  score: number;
};

export function ScoreCard({ label, score }: ScoreCardProps) {
  const percent = Math.round(score * 100);
  return (
    <div className="glass-card" data-testid={`score-card-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <p className="text-xs uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-bold text-neonGreen">{percent}%</p>
      <div className="mt-3 h-2 rounded-full bg-white/10">
        <div className="h-2 rounded-full bg-gradient-to-r from-neonBlue to-neonGreen" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
