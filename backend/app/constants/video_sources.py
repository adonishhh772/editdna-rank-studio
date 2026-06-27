from urllib.parse import urlparse

VIDEO_FORMAT_SHORTS = "shorts"
VIDEO_FORMAT_REGULAR = "regular"
VIDEO_FORMAT_UNKNOWN = "unknown"

VIDEO_ORIENTATION_MOBILE = "mobile"
VIDEO_ORIENTATION_LANDSCAPE = "landscape"
VIDEO_ORIENTATION_UNKNOWN = "unknown"

YOUTUBE_SEARCH_MODE_SHORTS = "shorts"
YOUTUBE_SEARCH_MODE_REGULAR = "regular"
YOUTUBE_SEARCH_MODE_ANY = "any"

MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
DEFAULT_RANKING_COUNT = 5
DEMO_DOWNLOAD_LIMIT = 1
MAX_PLATFORM_SEARCHES_PER_CONCEPT = 3
MAX_SEARCH_RESULTS_PER_QUERY = 8

VIDEO_URL_EXTENSIONS = (".mp4", ".webm", ".mov", ".mkv")

BLOCKED_PLATFORM_HOST_SUFFIXES = (
    "dailymotion.com",
)

PREFERRED_PLATFORM_HOST_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "vimeo.com",
)

PLATFORM_HOST_SUFFIXES = (
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
)

YOUTUBE_SEARCH_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "m.youtube.com",
)

TIKTOK_SEARCH_DOMAINS = (
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
)

PLATFORM_SEARCH_QUERIES_TIKTOK_SHORTS = (
    "{concept} {topic} tiktok",
    "{topic} {concept} tiktok raw",
    "{topic} tiktok story",
)

PLATFORM_SEARCH_QUERIES = (
    "{concept} {topic}",
    "{topic} {concept}",
    "{topic}",
)

PLATFORM_SEARCH_QUERIES_SHORTS = (
    "{concept} {topic} shorts",
    "{topic} {concept} youtube shorts",
    "{topic} shorts",
)

PLATFORM_SEARCH_QUERIES_REGULAR = (
    "{concept} {topic}",
    "{topic} {concept} full video",
    "{topic}",
)

ALLOWED_STOCK_SEARCH_DOMAINS = [
    "pexels.com",
    "pixabay.com",
]

ALLOWED_VIDEO_DOWNLOAD_HOSTS = frozenset(
    {
        "videos.pexels.com",
        "cdn.pixabay.com",
    }
)


def normalize_host(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_platform_video_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    host = normalize_host(url)
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in PLATFORM_HOST_SUFFIXES)


def is_blocked_platform_url(url: str) -> bool:
    host = normalize_host(url)
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in BLOCKED_PLATFORM_HOST_SUFFIXES)


def is_preferred_platform_url(url: str) -> bool:
    host = normalize_host(url)
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in PREFERRED_PLATFORM_HOST_SUFFIXES)


def is_downloadable_platform_url(url: str) -> bool:
    return is_platform_video_url(url) and not is_blocked_platform_url(url)


def platform_download_priority(url: str) -> int:
    if is_youtube_url(url):
        return 0
    if is_preferred_platform_url(url):
        return 1
    if is_downloadable_platform_url(url):
        return 2
    return 99


def is_youtube_url(url: str) -> bool:
    host = normalize_host(url)
    return host in {"youtube.com", "youtu.be", "m.youtube.com"} or host.endswith(".youtube.com")


def is_youtube_shorts_url(url: str) -> bool:
    if not is_youtube_url(url):
        return False
    parsed = urlparse(url)
    return parsed.path.lower().startswith("/shorts/")


def is_mobile_youtube_host(url: str) -> bool:
    return normalize_host(url) == "m.youtube.com"


def detect_youtube_video_format(url: str) -> str:
    if not is_youtube_url(url):
        return VIDEO_FORMAT_UNKNOWN
    if is_youtube_shorts_url(url):
        return VIDEO_FORMAT_SHORTS
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    if path_lower.startswith("/watch") or path_lower.startswith("/embed/") or path_lower.startswith("/live/"):
        return VIDEO_FORMAT_REGULAR
    if normalize_host(url) == "youtu.be" and path_lower.strip("/"):
        return VIDEO_FORMAT_REGULAR
    return VIDEO_FORMAT_UNKNOWN


def detect_video_orientation_from_url(url: str) -> str:
    if not url:
        return VIDEO_ORIENTATION_UNKNOWN
    if is_youtube_shorts_url(url) or is_mobile_youtube_host(url):
        return VIDEO_ORIENTATION_MOBILE
    if is_tiktok_url(url):
        return VIDEO_ORIENTATION_MOBILE
    youtube_format = detect_youtube_video_format(url)
    if youtube_format == VIDEO_FORMAT_REGULAR:
        return VIDEO_ORIENTATION_LANDSCAPE
    return VIDEO_ORIENTATION_UNKNOWN


def detect_video_orientation_from_dimensions(width: int | None, height: int | None) -> str:
    if width is None or height is None or width <= 0 or height <= 0:
        return VIDEO_ORIENTATION_UNKNOWN
    if height > width:
        return VIDEO_ORIENTATION_MOBILE
    if width > height:
        return VIDEO_ORIENTATION_LANDSCAPE
    return VIDEO_ORIENTATION_UNKNOWN


def resolve_youtube_search_mode(video_orientation: str) -> str:
    if video_orientation == VIDEO_ORIENTATION_MOBILE:
        return YOUTUBE_SEARCH_MODE_SHORTS
    if video_orientation == VIDEO_ORIENTATION_LANDSCAPE:
        return YOUTUBE_SEARCH_MODE_REGULAR
    return YOUTUBE_SEARCH_MODE_ANY


def is_tiktok_url(url: str) -> bool:
    host = normalize_host(url)
    return "tiktok.com" in host


def is_single_tiktok_video_url(url: str) -> bool:
    if not is_tiktok_url(url):
        return False
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    host = normalize_host(url)
    if host == "vm.tiktok.com" and path_lower.strip("/"):
        return True
    return "/video/" in path_lower


def platform_search_queries_for_mode(search_mode: str) -> tuple[str, ...]:
    if search_mode == YOUTUBE_SEARCH_MODE_SHORTS:
        return PLATFORM_SEARCH_QUERIES_SHORTS
    if search_mode == YOUTUBE_SEARCH_MODE_REGULAR:
        return PLATFORM_SEARCH_QUERIES_REGULAR
    return PLATFORM_SEARCH_QUERIES


def tiktok_search_queries() -> tuple[str, ...]:
    return PLATFORM_SEARCH_QUERIES_TIKTOK_SHORTS


def is_single_youtube_video_url(url: str) -> bool:
    if not is_youtube_url(url):
        return False

    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    query = parsed.query.lower()

    if "/playlist" in path_lower:
        return False
    if "/channel/" in path_lower or "/c/" in path_lower or path_lower.startswith("/@"):
        return False
    if "list=" in query and "v=" not in query:
        return False
    if path_lower.startswith("/shorts/") and len(path_lower.strip("/").split("/")) >= 2:
        return True
    if path_lower.startswith("/embed/") and len(path_lower.strip("/").split("/")) >= 2:
        return True
    if path_lower.startswith("/live/") and len(path_lower.strip("/").split("/")) >= 2:
        return True
    if "/watch" in path_lower and "v=" in query:
        return True
    if normalize_host(url) == "youtu.be" and path_lower.strip("/"):
        return True

    return False


def detect_platform_name(url: str) -> str:
    host = normalize_host(url)
    if "youtube" in host or host == "youtu.be":
        return "youtube"
    if "tiktok" in host:
        return "tiktok"
    if "instagram" in host:
        return "instagram"
    if host in {"twitter.com", "x.com"}:
        return "twitter"
    if "facebook" in host or host == "fb.watch":
        return "facebook"
    if "vimeo" in host:
        return "vimeo"
    return "web"


def is_direct_video_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in VIDEO_URL_EXTENSIONS):
        return True
    return "/video/" in path_lower


def is_video_url(url: str) -> bool:
    trimmed = url.strip()
    if not trimmed.startswith(("http://", "https://")):
        return False
    parsed = urlparse(trimmed)
    if not parsed.netloc:
        return False
    return is_platform_video_url(trimmed) or is_direct_video_url(trimmed)


def validate_reference_video_url(url: str) -> str:
    trimmed = url.strip()
    if not trimmed:
        raise ValueError("Video URL is required")
    if not trimmed.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    parsed = urlparse(trimmed)
    if not parsed.netloc:
        raise ValueError("URL is missing a valid host")
    if is_video_url(trimmed):
        return trimmed
    raise ValueError(
        "URL does not appear to be a video. Provide a direct video file link "
        "(.mp4, .webm, .mov, .mkv) or a link from YouTube, TikTok, Instagram, Vimeo, etc."
    )
