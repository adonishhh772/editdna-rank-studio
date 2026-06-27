import shutil
from pathlib import Path
from typing import Any

from app.config import get_settings


class AssetStore:
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}

    def __init__(self) -> None:
        self.settings = get_settings()

    def project_upload_dir(self, project_id: str) -> Path:
        path = self.settings.upload_dir / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def project_output_dir(self, project_id: str) -> Path:
        path = self.settings.output_dir / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_sample_assets(self) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        for file_path in sorted(self.settings.asset_library_dir.glob("*")):
            if file_path.suffix.lower() in self.VIDEO_EXTENSIONS:
                assets.append(
                    {
                        "filename": file_path.name,
                        "path": str(file_path),
                        "source_type": "sample_asset",
                    }
                )
        return assets

    def save_upload(self, project_id: str, filename: str, content: bytes) -> str:
        target = self.project_upload_dir(project_id) / filename
        target.write_bytes(content)
        return str(target)

    def copy_sample_asset(self, project_id: str, filename: str) -> str:
        source = self.settings.asset_library_dir / filename
        if not source.exists():
            raise FileNotFoundError(f"Sample asset not found: {filename}")
        target = self.project_upload_dir(project_id) / filename
        shutil.copy2(source, target)
        return str(target)

    def delete_project_assets(self, project_id: str) -> None:
        for root_dir in (self.settings.upload_dir, self.settings.output_dir):
            project_dir = root_dir / project_id
            if project_dir.exists():
                shutil.rmtree(project_dir)
