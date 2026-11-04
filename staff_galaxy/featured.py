"""The galaxy members whose dots become Bangumi avatars.

Union of two rankings over galaxy members:

- the BY_STRENGTH strongest by backbone weighted degree (the meta node order),
- the BY_DISCUSSION most discussed on Bangumi (person-page comment count).

The list is ordered by each person's better rank in either list, which is the
order the frontend uses to decide who keeps an avatar where they overlap.

    .venv/bin/python -m staff_galaxy.featured [--store data/deploy/staff_galaxy.sqlite]

recomputes it into an existing store; `staff_galaxy.export` does the same on
every export.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from .store import DEFAULT_STORE_PATH

BY_STRENGTH = 500
BY_DISCUSSION = 500


def build_featured_people(conn: sqlite3.Connection, meta: dict[str, Any]) -> list[str]:
    strength_rank = {node["id"]: rank for rank, node in enumerate(meta["nodes"])}
    discussed = conn.execute(
        """
        SELECT p.id FROM person p JOIN galaxy_node g ON g.id = p.id
        WHERE p.comments > 0
        ORDER BY p.comments DESC, p.collects DESC, p.id
        LIMIT ?
        """,
        (BY_DISCUSSION,),
    ).fetchall()
    best: dict[str, int] = {node_id: rank for node_id, rank in strength_rank.items() if rank < BY_STRENGTH}
    for rank, (person_id,) in enumerate(discussed):
        node_id = str(person_id)
        best[node_id] = min(rank, best.get(node_id, rank))
    return sorted(best, key=lambda node_id: (best[node_id], strength_rank[node_id]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute the avatar list inside a deploy store.")
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE_PATH)
    args = parser.parse_args()

    conn = sqlite3.connect(args.store)
    try:
        (graph_meta,) = conn.execute("SELECT value FROM meta WHERE key = 'graph_meta'").fetchone()
        people = build_featured_people(conn, json.loads(graph_meta))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('featured_people', ?)", (json.dumps(people).encode(),))
        conn.commit()
    finally:
        conn.close()
    print(f"Wrote {len(people)} featured people to {args.store}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
