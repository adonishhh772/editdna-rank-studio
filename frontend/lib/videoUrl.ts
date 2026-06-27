const VIDEO_EXTENSIONS = [".mp4", ".webm", ".mov", ".mkv"];

const PLATFORM_HOST_SUFFIXES = [
  "youtube.com",
  "youtu.be",
  "tiktok.com",
  "instagram.com",
  "twitter.com",
  "x.com",
  "facebook.com",
  "fb.watch",
  "vimeo.com",
  "dailymotion.com",
  "reddit.com",
  "twitch.tv",
  "linkedin.com",
];

function normalizeHost(url: string): string {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return "";
  }
}

function isPlatformVideoUrl(url: string): boolean {
  const host = normalizeHost(url);
  if (!host) {
    return false;
  }
  return PLATFORM_HOST_SUFFIXES.some((suffix) => host === suffix || host.endsWith(`.${suffix}`));
}

function isDirectVideoUrl(url: string): boolean {
  try {
    const path = new URL(url).pathname.toLowerCase();
    if (VIDEO_EXTENSIONS.some((ext) => path.endsWith(ext))) {
      return true;
    }
    return path.includes("/video/");
  } catch {
    return false;
  }
}

export function isVideoUrl(url: string): boolean {
  const trimmed = url.trim();
  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    return false;
  }
  try {
    const parsed = new URL(trimmed);
    if (!parsed.hostname) {
      return false;
    }
  } catch {
    return false;
  }
  return isPlatformVideoUrl(trimmed) || isDirectVideoUrl(trimmed);
}

export function validateVideoUrl(url: string): string | null {
  const trimmed = url.trim();
  if (!trimmed) {
    return "Video URL is required";
  }
  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    return "URL must start with http:// or https://";
  }
  try {
    const parsed = new URL(trimmed);
    if (!parsed.hostname) {
      return "URL is missing a valid host";
    }
  } catch {
    return "URL is not valid";
  }
  if (!isVideoUrl(trimmed)) {
    return "URL does not appear to be a video. Use a direct file link or a platform like YouTube or TikTok.";
  }
  return null;
}
