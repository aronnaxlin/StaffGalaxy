"""Export the Neo4j knowledge graph into the single-file deploy store (see store.py).

    .venv/bin/python -m staff_galaxy.export [--out data/deploy/staff_galaxy.sqlite]

Run after `staff_galaxy.cli`. The file is written next to the target and
renamed into place, so a running API never sees a half-written store.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, LiteralString

from neo4j import Driver

from .communities import build_community_labels
from .featured import build_featured_people
from .graph_buffers import build_graph_buffers
from .graph_db import connect_driver, connection_uri, latest_data_snapshot, read_one
from .search_index import extract_person_name_cn, extract_person_name_tw
from .store import DEFAULT_STORE_PATH, INDEXES, SCHEMA


@dataclass(frozen=True)
class ExportStats:
    persons: int
    anime: int
    credits: int
    galaxy_nodes: int
    collab_edges: int
    search_terms: int
    size_bytes: int


def _stream(driver: Driver, query: LiteralString) -> Iterator[list[Any]]:
    """Stream records instead of materializing ~1M rows through execute_query."""
    with driver.session() as session:
        for record in session.run(query):
            yield record.values()


def _insert(conn: sqlite3.Connection, table: str, rows: Iterator[Any], width: int) -> int:
    placeholders = ", ".join("?" * width)
    before = conn.total_changes
    conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
    return conn.total_changes - before


def export_store(driver: Driver, out_path: Path) -> ExportStats:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    tmp_path.unlink(missing_ok=True)

    conn = sqlite3.connect(tmp_path)
    try:
        conn.executescript("PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF;" + SCHEMA)

        persons = _insert(
            conn,
            "person",
            (
                (
                    person_id,
                    name or "",
                    extract_person_name_cn(infobox or ""),
                    extract_person_name_tw(infobox or ""),
                    career_json or "",
                    summary or "",
                    comments or 0,
                    collects or 0,
                )
                for person_id, name, infobox, career_json, summary, comments, collects in _stream(
                    driver,
                    """
                    MATCH (p:Person)
                    RETURN p.id, p.name, p.infobox, p.career_json, p.summary, p.comments, p.collects
                    """,
                )
            ),
            8,
        )
        anime = _insert(
            conn,
            "anime",
            (
                (anime_id, name or "", name_cn or "", date or "", year, bool(nsfw))
                for anime_id, name, name_cn, date, year, nsfw in _stream(
                    driver, "MATCH (a:Anime) RETURN a.id, a.name, a.name_cn, a.date, a.year, a.nsfw"
                )
            ),
            6,
        )
        credits = _insert(
            conn,
            "credit",
            _stream(
                driver,
                """
                MATCH (p:Person)-[c:CREDITED]->(a:Anime)
                RETURN p.id, a.id, c.position_id, c.raw_position, c.position_cn, c.position_en,
                       c.normalized_role, c.role_tier, c.role_weight, c.appear_eps,
                       coalesce(a.nsfw, false)
                """,
            ),
            11,
        )
        galaxy_nodes = _insert(
            conn,
            "galaxy_node",
            _stream(
                driver,
                """
                MATCH (g:GalaxyNode)
                RETURN g.id, coalesce(g.visible_degree, 0), coalesce(g.visible_weighted_degree, 0.0),
                       g.node_size, g.role_layer
                """,
            ),
            5,
        )
        collab_edges = _insert(
            conn,
            "collab",
            _stream(
                driver,
                """
                MATCH (s:GalaxyNode)-[e:COLLAB]->(t:GalaxyNode)
                RETURN s.id, t.id, e.shared_works_count, e.collaboration_score,
                       e.first_year, e.last_year, e.selection_reason
                """,
            ),
            7,
        )
        search_terms = _insert(
            conn,
            "search_term",
            _stream(
                driver,
                """
                MATCH (g:GalaxyNode)-[:HAS_SEARCH_TERM]->(t:SearchTerm)
                RETURN g.id, t.norm, t.compact
                """,
            ),
            3,
        )

        snapshot = latest_data_snapshot(driver)
        geometry = read_one(
            driver,
            """
            MATCH (g:GalaxyNode)
            RETURN count(g) AS nodes,
                   coalesce(max(g.layout_method), 'unknown') AS layout_method,
                   // Position checksum: the frontend's cache-buster for buffers/meta.
                   round(coalesce(sum(g.x * g.x + g.y * g.y), 0.0), 2) AS fingerprint
            """,
        ) or {"nodes": 0, "layout_method": "unknown", "fingerprint": 0.0}
        graph_info = {
            "nodes": int(geometry["nodes"]),
            "edges": collab_edges,
            "layoutMethod": str(geometry["layout_method"]),
            "geometryFingerprint": float(geometry["fingerprint"]),
        }
        buffers = build_graph_buffers(driver)
        graph_meta = json.dumps({**buffers.meta, "snapshot": snapshot}, ensure_ascii=False)
        community_labels = build_community_labels(conn, buffers.payload, buffers.meta)
        featured_people = build_featured_people(conn, buffers.meta)
        conn.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("snapshot", json.dumps(snapshot, ensure_ascii=False) if snapshot else None),
                ("graph", json.dumps(graph_info)),
                ("graph_buffers", buffers.payload),
                ("graph_meta", graph_meta.encode()),
                ("community_labels", json.dumps(community_labels, ensure_ascii=False).encode()),
                ("featured_people", json.dumps(featured_people).encode()),
            ],
        )

        conn.executescript(INDEXES + "ANALYZE;")
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()

    os.replace(tmp_path, out_path)
    return ExportStats(
        persons=persons,
        anime=anime,
        credits=credits,
        galaxy_nodes=galaxy_nodes,
        collab_edges=collab_edges,
        search_terms=search_terms,
        size_bytes=out_path.stat().st_size,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the Neo4j graph into the SQLite deploy store.")
    parser.add_argument("--out", type=Path, default=DEFAULT_STORE_PATH)
    args = parser.parse_args()

    driver = connect_driver()  # loads .env, which may set NEO4J_URI
    print(f"Reading Neo4j graph: {connection_uri()}", flush=True)
    started = time.perf_counter()
    try:
        driver.verify_connectivity()
        stats = export_store(driver, args.out)
    finally:
        driver.close()
    print(
        f"Wrote {args.out} ({stats.size_bytes / 1e6:.1f} MB) in {time.perf_counter() - started:.0f}s: "
        f"{stats.persons:,} people, {stats.anime:,} anime, {stats.credits:,} credits, "
        f"{stats.galaxy_nodes:,} galaxy nodes, {stats.collab_edges:,} COLLAB edges, "
        f"{stats.search_terms:,} search terms.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
