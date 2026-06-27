import re
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.constants.demo import VALID_DEMO_MODES


@dataclass(frozen=True)
class DemoPack:
    pack_id: str
    pack_dir: Path
    youtube_url: str
    topic: str
    project_title: str | None
    rank_concepts: dict[int, str]
    reject_concepts: dict[int, str]
    reject_demo_slot: int | None
    candidate_files: dict[int, Path]
    reject_files: dict[int, Path]
    reject_fallback_path: Path | None
    final_output_path: Path
    ranking_count: int


_NOTES_YOUTUBE_PATTERN = re.compile(
    r"youtube_url\s*=\s*(https?://\S+)",
    re.IGNORECASE,
)
_NOTES_TOPIC_PATTERN = re.compile(
    r"^topic\s*=\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_NOTES_PROJECT_TITLE_PATTERN = re.compile(
    r"^project_title\s*=\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_NOTES_RANK_CONCEPT_PATTERN = re.compile(
    r"^rank_(\d+)\s*=\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_NOTES_RANK_REJECT_CONCEPT_PATTERN = re.compile(
    r"^rank_(\d+)_reject\s*=\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_NOTES_REJECT_DEMO_SLOT_PATTERN = re.compile(
    r"^reject_demo_slot\s*=\s*(\d+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_RANK_FILE_PATTERN = re.compile(r"^rank_(\d+)\.(mp4|mov|webm|mkv)$", re.IGNORECASE)
_RANK_REJECT_FILE_PATTERN = re.compile(
    r"^rank_(\d+)_reject(?:ed)?\.(mp4|mov|webm|mkv)$",
    re.IGNORECASE,
)
_REJECT_FALLBACK_FILENAME = "reject_sample.mp4"


def is_demo_mode_active() -> bool:
    settings = get_settings()
    return settings.demo_mode in VALID_DEMO_MODES


def resolve_demo_pack_dir(pack_id: str) -> Path:
    settings = get_settings()
    return settings.demo_packs_dir / pack_id


def load_demo_pack(pack_id: str) -> DemoPack:
    if pack_id not in VALID_DEMO_MODES:
        raise ValueError(f"Unknown demo pack: {pack_id}")

    pack_dir = resolve_demo_pack_dir(pack_id)
    if not pack_dir.is_dir():
        raise FileNotFoundError(f"Demo pack directory not found: {pack_dir}")

    notes_path = pack_dir / "notes.txt"
    if not notes_path.exists():
        raise FileNotFoundError(f"Demo pack notes missing: {notes_path}")

    notes_text = notes_path.read_text(encoding="utf-8")
    youtube_match = _NOTES_YOUTUBE_PATTERN.search(notes_text)
    topic_match = _NOTES_TOPIC_PATTERN.search(notes_text)
    if youtube_match is None:
        raise ValueError(f"youtube_url missing in {notes_path}")
    if topic_match is None:
        raise ValueError(f"topic missing in {notes_path}")

    project_title_match = _NOTES_PROJECT_TITLE_PATTERN.search(notes_text)
    project_title = project_title_match.group(1).strip() if project_title_match else None

    rank_concepts: dict[int, str] = {}
    for rank_match in _NOTES_RANK_CONCEPT_PATTERN.finditer(notes_text):
        rank_concepts[int(rank_match.group(1))] = rank_match.group(2).strip()

    reject_concepts: dict[int, str] = {}
    for rank_match in _NOTES_RANK_REJECT_CONCEPT_PATTERN.finditer(notes_text):
        reject_concepts[int(rank_match.group(1))] = rank_match.group(2).strip()

    reject_demo_slot: int | None = None
    reject_slot_match = _NOTES_REJECT_DEMO_SLOT_PATTERN.search(notes_text)
    if reject_slot_match is not None:
        reject_demo_slot = int(reject_slot_match.group(1))

    candidates_dir = pack_dir / "candidates"
    if not candidates_dir.is_dir():
        raise FileNotFoundError(f"Demo candidates directory missing: {candidates_dir}")

    candidate_files: dict[int, Path] = {}
    reject_files: dict[int, Path] = {}
    for file_path in sorted(candidates_dir.iterdir()):
        if not file_path.is_file():
            continue
        reject_match = _RANK_REJECT_FILE_PATTERN.match(file_path.name)
        if reject_match is not None:
            reject_files[int(reject_match.group(1))] = file_path
            continue
        rank_match = _RANK_FILE_PATTERN.match(file_path.name)
        if rank_match is not None:
            candidate_files[int(rank_match.group(1))] = file_path

    reject_fallback_path = candidates_dir / _REJECT_FALLBACK_FILENAME
    if not reject_fallback_path.exists():
        reject_fallback_path = None

    if not candidate_files:
        raise FileNotFoundError(f"No rank_*.mp4 files found in {candidates_dir}")

    final_output_path = pack_dir / "final_output.mp4"
    if not final_output_path.exists():
        raise FileNotFoundError(f"Demo final output missing: {final_output_path}")

    return DemoPack(
        pack_id=pack_id,
        pack_dir=pack_dir,
        youtube_url=youtube_match.group(1).strip(),
        topic=topic_match.group(1).strip(),
        project_title=project_title,
        rank_concepts=rank_concepts,
        reject_concepts=reject_concepts,
        reject_demo_slot=reject_demo_slot,
        candidate_files=candidate_files,
        reject_files=reject_files,
        reject_fallback_path=reject_fallback_path,
        final_output_path=final_output_path,
        ranking_count=len(candidate_files),
    )


def get_active_demo_pack() -> DemoPack:
    settings = get_settings()
    if settings.demo_mode not in VALID_DEMO_MODES:
        raise RuntimeError("Demo mode is not active")
    return load_demo_pack(settings.demo_mode)
