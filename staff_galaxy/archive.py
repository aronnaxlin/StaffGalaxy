from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_ARCHIVE_FILES = {
    "subject.jsonlines",
    "person.jsonlines",
    "character.jsonlines",
    "subject-persons.jsonlines",
    "person-characters.jsonlines",
}


@dataclass(frozen=True)
class ArchiveInput:
    zip_path: Path
    latest_metadata: dict[str, object] | None


def detect_archive_zip(raw_dir: Path, explicit_zip: Path | None = None) -> ArchiveInput:
    if explicit_zip is not None:
        return _validate_archive_zip(explicit_zip, None)

    latest_path = raw_dir / "bangumi-archive" / "aux" / "latest.json"
    latest_metadata: dict[str, object] | None = None
    latest_name: str | None = None
    if latest_path.exists():
        latest_metadata = json.loads(latest_path.read_text(encoding="utf-8"))
        name = latest_metadata.get("name")
        if isinstance(name, str):
            latest_name = name

    candidates = sorted(raw_dir.glob("dump-*.zip"), reverse=True)
    if latest_name:
        latest_candidate = raw_dir / latest_name
        if latest_candidate.exists():
            return _validate_archive_zip(latest_candidate, latest_metadata)

    if not candidates:
        raise FileNotFoundError(
            f"No Bangumi Archive dump zip found under {raw_dir}. "
            "Expected a file like dump-YYYY-MM-DD.HHMMSSZ.zip."
        )
    return _validate_archive_zip(candidates[0], latest_metadata)


def iter_jsonlines(zip_path: Path, member: str) -> Iterable[dict[str, object]]:
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(member) as file_obj:
            for line_number, raw_line in enumerate(file_obj, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON in {zip_path}:{member}:{line_number}: {exc}"
                    ) from exc


def _validate_archive_zip(
    zip_path: Path, latest_metadata: dict[str, object] | None
) -> ArchiveInput:
    if not zip_path.exists():
        raise FileNotFoundError(f"Archive zip does not exist: {zip_path}")
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    missing = sorted(REQUIRED_ARCHIVE_FILES - names)
    if missing:
        raise ValueError(
            f"Archive zip {zip_path} is missing required files: {', '.join(missing)}"
        )
    return ArchiveInput(zip_path=zip_path, latest_metadata=latest_metadata)
