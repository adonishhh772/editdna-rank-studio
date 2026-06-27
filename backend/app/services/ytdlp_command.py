import shutil
import subprocess
import sys
from pathlib import Path


YTDLP_REMOTE_COMPONENTS = ("ejs:github",)
YTDLP_MIN_NODE_MAJOR = 20
YTDLP_IMPERSONATE_TARGET = "chrome"


def impersonation_available() -> bool:
    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        return False
    return True


def resolve_impersonate_target() -> str | None:
    if not impersonation_available():
        return None
    return YTDLP_IMPERSONATE_TARGET


def resolve_js_runtime() -> tuple[str, str] | None:
    node_candidates = [
        Path("/opt/homebrew/opt/node@22/bin/node"),
        Path("/opt/homebrew/opt/node@20/bin/node"),
        Path("/usr/local/opt/node@22/bin/node"),
        Path("/usr/local/opt/node@20/bin/node"),
    ]

    node_from_path = shutil.which("node")
    if node_from_path:
        node_candidates.insert(0, Path(node_from_path))

    for node_path in node_candidates:
        if not node_path.is_file():
            continue
        try:
            version_result = subprocess.run(
                [str(node_path), "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        version_text = version_result.stdout.strip().lstrip("v")
        if not version_text:
            continue
        major_version = int(version_text.split(".", maxsplit=1)[0])
        if major_version >= YTDLP_MIN_NODE_MAJOR:
            return "node", str(node_path)

    deno_path = shutil.which("deno")
    if deno_path:
        return "deno", deno_path

    return None


def resolve_ytdlp_executable() -> list[str]:
    ytdlp_path = shutil.which("yt-dlp")
    if ytdlp_path:
        return [ytdlp_path]
    return [sys.executable, "-m", "yt_dlp"]


def build_ytdlp_base_args() -> list[str]:
    args = [*resolve_ytdlp_executable(), "--no-playlist"]

    js_runtime = resolve_js_runtime()
    if js_runtime is not None:
        runtime_name, runtime_path = js_runtime
        args.extend(["--js-runtimes", f"{runtime_name}:{runtime_path}"])

    for component in YTDLP_REMOTE_COMPONENTS:
        args.extend(["--remote-components", component])

    impersonate_target = resolve_impersonate_target()
    if impersonate_target is not None:
        args.extend(["--impersonate", impersonate_target])

    return args


def build_ytdlp_download_args(
    output_template: str,
    page_url: str,
    *,
    max_filesize: str = "100M",
    format_selector: str = "best[height<=1080][ext=mp4]/best[ext=mp4]/best",
) -> list[str]:
    return [
        *build_ytdlp_base_args(),
        "--merge-output-format",
        "mp4",
        "-f",
        format_selector,
        "--max-filesize",
        max_filesize,
        "-o",
        output_template,
        page_url,
    ]


def build_ytdlp_probe_args(page_url: str) -> list[str]:
    return [
        *build_ytdlp_base_args(),
        "--dump-single-json",
        "--skip-download",
        page_url,
    ]
