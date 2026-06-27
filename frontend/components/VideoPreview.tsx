"use client";

type VideoPreviewProps = {
  title: string;
  src: string | null;
};

export function VideoPreview({ title, src }: VideoPreviewProps) {
  return (
    <div className="glass-card" data-testid="video-preview">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">{title}</h3>
      {src ? (
        <video
          src={src}
          controls
          preload="metadata"
          className="aspect-[9/16] w-full max-w-md rounded-xl bg-black"
        />
      ) : (
        <div className="flex aspect-[9/16] w-full max-w-md items-center justify-center rounded-xl border border-dashed border-white/10 bg-black/30 text-sm text-slate-500">
          No video available
        </div>
      )}
    </div>
  );
}
