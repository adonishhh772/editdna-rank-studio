Optional local fallback clips.

The swarm primarily discovers candidate videos from the open web:
YouTube, TikTok, Instagram, X/Twitter, Facebook, Vimeo, Reddit, and other platforms supported by **yt-dlp**.

Tavily searches for relevant URLs, yt-dlp downloads them into `uploads/{project_id}/candidates/`, and Gemini analyses the footage.

Ensure `yt-dlp` is installed:

```bash
pip install yt-dlp
# or
brew install yt-dlp
```
