"""One-shot migration: record the Bangumi Archive snapshot used by the local DB."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from staff_galaxy.archive import detect_archive_zip  # noqa: E402
from staff_galaxy.database import connect_database, record_data_snapshot  # noqa: E402


def migrate(db_path: Path, raw_dir: Path, archive_zip: Path | None) -> None:
    archive = detect_archive_zip(raw_dir, archive_zip)
    metadata = archive.latest_metadata or {}
    created_at = metadata.get("created_at")
    source_url = metadata.get("browser_download_url")

    conn = connect_database(db_path)
    try:
        record_data_snapshot(
            conn,
            archive_name=archive.zip_path.name,
            archive_created_at=created_at if isinstance(created_at, str) else "",
            archive_size_bytes=archive.zip_path.stat().st_size,
            source_url=source_url if isinstance(source_url, str) else "",
        )
        print(f"Recorded current data snapshot: {archive.zip_path.name}", flush=True)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Record Staff Galaxy data snapshot metadata.")
    parser.add_argument("--db", type=Path, default=Path("data/processed/staff_galaxy.duckdb"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--archive-zip", type=Path)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found: {args.db}", file=sys.stderr)
        return 1

    migrate(args.db, args.raw_dir, args.archive_zip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
