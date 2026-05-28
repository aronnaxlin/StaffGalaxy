"""One-shot migration: add person infobox aliases and rebuild search terms."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from staff_galaxy.database import (  # noqa: E402
    connect_database,
    create_indexes,
    create_supporting_views,
    ensure_person_infobox,
)
from staff_galaxy.search_index import build_person_search_terms  # noqa: E402


def latest_person_jsonlines(extract_root: Path) -> Path:
    candidates = sorted(extract_root.glob("dump-*/person.jsonlines"))
    if not candidates:
        raise FileNotFoundError(f"No person.jsonlines found under {extract_root}")
    return candidates[-1]


def migrate(db_path: Path, person_jsonlines: Path) -> None:
    conn = connect_database(db_path)
    try:
        ensure_person_infobox(conn)

        rows: list[tuple[str, int]] = []
        with person_jsonlines.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                item = json.loads(line)
                person_id = item.get("id")
                if person_id is None:
                    continue
                rows.append((str(item.get("infobox") or ""), int(person_id)))

        print(f"Updating {len(rows):,} person infobox rows from {person_jsonlines}...", flush=True)
        conn.executemany(
            """
            UPDATE persons
            SET infobox = ?
            WHERE id = ?
            """,
            rows,
        )

        stats = build_person_search_terms(conn)
        create_supporting_views(conn)
        create_indexes(conn)
        print(
            f"Search index rebuilt: {stats.term_count:,} terms across "
            f"{stats.person_count:,} real people.",
            flush=True,
        )
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Staff Galaxy person search terms.")
    parser.add_argument("--db", type=Path, default=Path("data/processed/staff_galaxy.duckdb"))
    parser.add_argument("--person-jsonlines", type=Path)
    parser.add_argument("--extract-root", type=Path, default=Path("data/processed/extracted"))
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found: {args.db}", file=sys.stderr)
        return 1

    person_jsonlines = args.person_jsonlines or latest_person_jsonlines(args.extract_root)
    if not person_jsonlines.exists():
        print(f"person.jsonlines not found: {person_jsonlines}", file=sys.stderr)
        return 1

    migrate(args.db, person_jsonlines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
