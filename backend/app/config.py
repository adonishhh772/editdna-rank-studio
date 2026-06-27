import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.gemini_api_key: str = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("DEEPMIND_API_KEY")
            or ""
        )
        self.google_api_key: str = os.getenv("GOOGLE_API_KEY") or ""
        self.tavily_api_key: str = os.getenv("TAVILY_API_KEY") or ""
        self.slng_api_key: str = os.getenv("SLNG_API_KEY") or ""
        self.mubit_api_key: str = os.getenv("MUBIT_API_KEY") or ""
        self.mubit_project_id: str = os.getenv("MUBIT_PROJECT_ID") or "editdna-rank-studio"
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./editdna.db")
        self.upload_dir: Path = ROOT_DIR / os.getenv("UPLOAD_DIR", "./uploads")
        self.output_dir: Path = ROOT_DIR / os.getenv("OUTPUT_DIR", "./outputs")
        self.asset_library_dir: Path = ROOT_DIR / os.getenv("ASSET_LIBRARY_DIR", "./sample_assets")
        self.allow_demo_fallback: bool = os.getenv("ALLOW_DEMO_FALLBACK", "false").lower() == "true"
        self.gemini_reference_model: str = os.getenv("GEMINI_REFERENCE_MODEL", "gemini-2.5-flash")
        self.gemini_candidate_model: str = os.getenv("GEMINI_CANDIDATE_MODEL", "gemini-2.5-flash")
        self.slng_base_url: str = os.getenv("SLNG_BASE_URL", "https://api.slng.ai")
        self.mubit_endpoint: str = os.getenv("MUBIT_ENDPOINT", "https://api.mubit.ai")
        self.mubit_transport: str = os.getenv("MUBIT_TRANSPORT", "http")
        self.allow_web_video_fetch: bool = os.getenv("ALLOW_WEB_VIDEO_FETCH", "true").lower() == "true"

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.asset_library_dir.mkdir(parents=True, exist_ok=True)

    def missing_keys(self) -> list[str]:
        missing: list[str] = []
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if not self.tavily_api_key:
            missing.append("TAVILY_API_KEY")
        if not self.slng_api_key:
            missing.append("SLNG_API_KEY")
        if not self.mubit_api_key:
            missing.append("MUBIT_API_KEY")
        return missing

    def require_key(self, key_name: str) -> None:
        mapping = {
            "GEMINI_API_KEY": self.gemini_api_key,
            "TAVILY_API_KEY": self.tavily_api_key,
            "SLNG_API_KEY": self.slng_api_key,
            "MUBIT_API_KEY": self.mubit_api_key,
        }
        if not mapping.get(key_name):
            raise RuntimeError(f"Missing {key_name}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
