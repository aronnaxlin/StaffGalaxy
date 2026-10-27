"""Neo4j connection, schema, and shared write helpers.

Knowledge-graph schema (see AGENTS.md "Graph Schema"):

    (:Person {id, name, infobox, career_json, summary})
    (:Anime {id, name, name_cn, date, year, platform, score, rank, collects})
    (:Position {position_id, cn, en, jp, normalized_role, role_tier, role_weight})
    (:Character {id, name, role, summary})
    (:SearchTerm {person_id, term, norm, compact, kind})
    (:DataSnapshot {snapshot_id, archive_name, ...})

    (:Person)-[:CREDITED {position_id, raw_position, position_cn, position_en,
                          position_jp, normalized_role, role_tier, role_weight,
                          appear_eps}]->(:Anime)
    (:Person)-[:VOICED {subject_id, person_character_type, summary}]->(:Character)
    (:Character)-[:APPEARS_IN]->(:Anime)
    (:Person)-[:HAS_SEARCH_TERM]->(:SearchTerm)

Derived galaxy layer (rebuilt from CREDITED, never source of truth):

    (:Person:GalaxyNode {community_id, x, y, visible_degree,
                         visible_weighted_degree, node_size, role_layer, layout_method})
    (:Person)-[:COLLAB {shared_works_count, collaboration_score, first_year,
                        last_year, role_layer, expected_shared_works,
                        significance, selection_reason}]->(:Person)   # source id < target id

    selection_reason is 'bicm_significant' (BiCM-validated, FDR-controlled) or
    'spanning_forest' (topology-preserving strongest tie); see visible_edges.py.

The complete collaboration graph (~34M person pairs) is not materialized: any
pair's shared works, score, and shortest paths are derived from CREDITED.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator, Sequence
from itertools import islice
from pathlib import Path
from typing import Any

from neo4j import Driver, GraphDatabase


DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"
WRITE_BATCH_SIZE = 10_000

_driver: Driver | None = None


def load_env_file(path: Path = Path(".env")) -> None:
    """Populate os.environ from a KEY=VALUE .env file without overriding the shell."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def connection_uri() -> str:
    return os.environ.get("NEO4J_URI", DEFAULT_URI)


def connect_driver() -> Driver:
    load_env_file()
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD is not set (expected in the environment or .env)")
    return GraphDatabase.driver(
        connection_uri(),
        auth=(os.environ.get("NEO4J_USER", DEFAULT_USER), password),
    )


def get_driver() -> Driver:
    """Process-wide driver; the neo4j driver is thread-safe and pools connections."""
    global _driver
    if _driver is None:
        _driver = connect_driver()
    return _driver


def set_driver(driver: Driver | None) -> None:
    """Swap the process-wide driver (tests point the API at a scratch instance)."""
    global _driver
    _driver = driver


def read(driver: Driver, query: str, **params: Any) -> list[dict[str, Any]]:
    records, _, _ = driver.execute_query(query, params, routing_="r")
    return [record.data() for record in records]


def read_one(driver: Driver, query: str, **params: Any) -> dict[str, Any] | None:
    rows = read(driver, query, **params)
    return rows[0] if rows else None


def write(driver: Driver, query: str, **params: Any) -> None:
    driver.execute_query(query, params)


def _chunks(rows: Iterable[Any], size: int) -> Iterator[list[Any]]:
    iterator = iter(rows)
    while batch := list(islice(iterator, size)):
        yield batch


def write_batches(
    driver: Driver,
    query: str,
    rows: Iterable[dict[str, Any]],
    *,
    batch_size: int = WRITE_BATCH_SIZE,
) -> int:
    """Run `UNWIND $rows AS row ...` once per batch; returns rows written."""
    total = 0
    for batch in _chunks(rows, batch_size):
        driver.execute_query(query, {"rows": batch})
        total += len(batch)
    return total


CONSTRAINTS: Sequence[str] = (
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (n:Person) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT anime_id IF NOT EXISTS FOR (n:Anime) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT character_id IF NOT EXISTS FOR (n:Character) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT position_id IF NOT EXISTS FOR (n:Position) REQUIRE n.position_id IS UNIQUE",
    "CREATE CONSTRAINT snapshot_id IF NOT EXISTS FOR (n:DataSnapshot) REQUIRE n.snapshot_id IS UNIQUE",
    # RANGE indexes serve exact / STARTS WITH; TEXT indexes serve CONTAINS.
    "CREATE INDEX search_term_compact IF NOT EXISTS FOR (n:SearchTerm) ON (n.compact)",
    "CREATE INDEX search_term_norm IF NOT EXISTS FOR (n:SearchTerm) ON (n.norm)",
    "CREATE TEXT INDEX search_term_compact_text IF NOT EXISTS FOR (n:SearchTerm) ON (n.compact)",
    "CREATE TEXT INDEX search_term_norm_text IF NOT EXISTS FOR (n:SearchTerm) ON (n.norm)",
)


def create_constraints(driver: Driver) -> None:
    for statement in CONSTRAINTS:
        write(driver, statement)
    write(driver, "CALL db.awaitIndexes(300)")


def run_in_transactions(driver: Driver, query: str, **params: Any) -> None:
    """Run a `CALL { ... } IN TRANSACTIONS` query, which needs an implicit transaction."""
    with driver.session() as session:
        session.run(query, params).consume()


def clear_database(driver: Driver) -> None:
    """Delete every node and relationship in bounded transactions."""
    run_in_transactions(
        driver,
        "MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS",
    )


def record_data_snapshot(
    driver: Driver,
    *,
    archive_name: str,
    archive_created_at: str,
    archive_size_bytes: int,
    source_url: str,
) -> None:
    write(
        driver,
        """
        MERGE (s:DataSnapshot {snapshot_id: 'current'})
        SET s.archive_name = $archive_name,
            s.archive_created_at = $archive_created_at,
            s.archive_size_bytes = $archive_size_bytes,
            s.built_at = toString(localdatetime({timezone: 'UTC'})),
            s.source_url = $source_url
        """,
        archive_name=archive_name,
        archive_created_at=archive_created_at,
        archive_size_bytes=archive_size_bytes,
        source_url=source_url,
    )


def latest_data_snapshot(driver: Driver) -> dict[str, Any] | None:
    row = read_one(
        driver,
        """
        MATCH (s:DataSnapshot)
        RETURN s.snapshot_id AS snapshotId,
               s.archive_name AS archiveName,
               s.archive_created_at AS archiveCreatedAt,
               s.archive_size_bytes AS archiveSizeBytes,
               s.built_at AS builtAt,
               s.source_url AS sourceUrl
        ORDER BY s.built_at DESC
        LIMIT 1
        """,
    )
    if row is None:
        return None
    row["archiveSizeBytes"] = int(row["archiveSizeBytes"] or 0)
    return row
