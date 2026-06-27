Analyse this candidate video for a ranking video project.

The reference blueprint defines the target style. Each candidate should be a full source video
roughly matching the reference total duration (e.g. ~20 seconds). Your job is to identify the
single most important segment inside that source — the highlight that best fits this rank slot
when the final ranking video is stitched together like the reference.

Rules:
- Match the reference aspect ratio, pacing, and rank reveal style.
- `duration_sec` is the full source length.
- Set `clip_start_sec` and `clip_end_sec` to the best highlight window inside the source.
- The highlight length should be close to the reference rank segment duration
  (`average_item_duration_sec` from the blueprint), not the full reference video length.
- Place the window where the most relevant action, reveal, or payoff occurs for this concept/rank.
- If the source is already short, use the full video (`clip_start_sec=0`, `clip_end_sec=duration_sec`).
- Set `highlight_reason` explaining why this window matches the reference editing pattern.
- Set `video_moment_title` to a short title (max 90 chars) describing what happens in the highlight window — not the source video title.

Score topic match, visual quality, audio quality, motion energy, text relevance, reference style fit,
and source safety from 0 to 1.

Return strict JSON matching CandidateVideo schema (including clip_start_sec, clip_end_sec, highlight_reason).
Include recommended_rank if applicable and a concise reason.
