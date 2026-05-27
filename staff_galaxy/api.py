from __future__ import annotations

import os
import math
from pathlib import Path
from typing import Any

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


DEFAULT_DB_PATH = Path("data/processed/staff_galaxy.duckdb")

LEVELS: dict[str, dict[str, int]] = {
    "global": {"min_degree": 0, "min_shared": 12},
    "l0": {"min_degree": 150, "min_shared": 1},
    "l1": {"min_degree": 50, "min_shared": 3},
}


def get_db_path() -> Path:
    return Path(os.environ.get("STAFF_GALAXY_DB", DEFAULT_DB_PATH))


def connect_readonly() -> duckdb.DuckDBPyConnection:
    path = get_db_path()
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"DuckDB database not found: {path}. Run scripts/audit_data.py first.",
        )
    return duckdb.connect(str(path), read_only=True)


def row_dicts(rows: list[tuple[Any, ...]], columns: list[str]) -> list[dict[str, Any]]:
    return [dict(zip(columns, row, strict=True)) for row in rows]


app = FastAPI(title="Staff Galaxy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/manifest")
def manifest() -> dict[str, Any]:
    with connect_readonly() as conn:
        level_counts = {}
        for level, config in LEVELS.items():
            min_degree = config["min_degree"]
            min_shared = config["min_shared"]
            node_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM graph_nodes
                WHERE visible_degree >= ?
                """,
                [min_degree],
            ).fetchone()[0]
            edge_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM visible_person_edges e
                JOIN graph_nodes s ON e.source_person_id = s.person_id
                JOIN graph_nodes t ON e.target_person_id = t.person_id
                WHERE s.visible_degree >= ?
                  AND t.visible_degree >= ?
                  AND e.shared_works_count >= ?
                """,
                [min_degree, min_degree, min_shared],
            ).fetchone()[0]
            level_counts[level] = {"nodes": node_count, "edges": edge_count, **config}

    return {"version": 1, "db_path": str(get_db_path()), "levels": level_counts}


@app.get("/api/graph/{level}/nodes")
def graph_nodes(level: str) -> list[dict[str, Any]]:
    if level not in LEVELS:
        raise HTTPException(status_code=404, detail=f"Unknown graph level: {level}")

    min_degree = LEVELS[level]["min_degree"]
    with connect_readonly() as conn:
        rows = conn.execute(
            """
            SELECT
              g.person_id::TEXT AS id,
              p.name,
              ROUND(g.x, 3) AS x,
              ROUND(g.y, 3) AS y,
              g.visible_degree AS degree,
              g.visible_weighted_degree,
              g.node_size,
              g.role_layer
            FROM graph_nodes g
            JOIN persons p ON g.person_id = p.id
            WHERE g.visible_degree >= ?
            ORDER BY g.visible_degree DESC, g.visible_weighted_degree DESC, g.person_id
            """,
            [min_degree],
        ).fetchall()

    return row_dicts(
        rows,
        ["id", "name", "x", "y", "degree", "visibleWeightedDegree", "nodeSize", "roleLayer"],
    )


@app.get("/api/graph/{level}/edges")
def graph_edges(level: str) -> list[dict[str, Any]]:
    if level not in LEVELS:
        raise HTTPException(status_code=404, detail=f"Unknown graph level: {level}")

    config = LEVELS[level]
    with connect_readonly() as conn:
        rows = conn.execute(
            """
            SELECT
              e.source_person_id::TEXT AS source,
              e.target_person_id::TEXT AS target,
              e.shared_works_count AS w,
              e.collaboration_score,
              e.first_year,
              e.last_year,
              e.selection_reason
            FROM visible_person_edges e
            JOIN graph_nodes s ON e.source_person_id = s.person_id
            JOIN graph_nodes t ON e.target_person_id = t.person_id
            WHERE s.visible_degree >= ?
              AND t.visible_degree >= ?
              AND e.shared_works_count >= ?
            ORDER BY e.shared_works_count DESC, e.collaboration_score DESC
            """,
            [config["min_degree"], config["min_degree"], config["min_shared"]],
        ).fetchall()

    return row_dicts(
        rows,
        ["source", "target", "w", "collaborationScore", "firstYear", "lastYear", "selectionReason"],
    )


@app.get("/api/person/{person_id}/galaxy")
def person_galaxy(
    person_id: int,
    limit: int = Query(default=220, ge=1, le=600),
    min_shared: int = Query(default=1, ge=1, le=1000),
) -> dict[str, Any]:
    with connect_readonly() as conn:
        center = conn.execute(
            """
            SELECT
              g.person_id::TEXT AS id,
              p.name,
              g.visible_degree AS degree,
              g.visible_weighted_degree,
              g.node_size,
              g.role_layer
            FROM graph_nodes g
            JOIN persons p ON g.person_id = p.id
            WHERE g.person_id = ?
            """,
            [person_id],
        ).fetchone()
        if center is None:
            raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

        neighbors = conn.execute(
            """
            WITH incident AS (
              SELECT
                CASE
                  WHEN e.source_person_id = ? THEN e.target_person_id
                  ELSE e.source_person_id
                END AS neighbor_id,
                e.shared_works_count,
                e.collaboration_score,
                e.first_year,
                e.last_year,
                e.selection_reason
              FROM visible_person_edges e
              WHERE (e.source_person_id = ? OR e.target_person_id = ?)
                AND e.shared_works_count >= ?
              ORDER BY e.shared_works_count DESC, e.collaboration_score DESC, neighbor_id
              LIMIT ?
            )
            SELECT
              i.neighbor_id::TEXT AS id,
              p.name,
              g.visible_degree AS degree,
              g.visible_weighted_degree,
              g.node_size,
              g.role_layer,
              i.shared_works_count,
              i.collaboration_score,
              i.first_year,
              i.last_year,
              i.selection_reason
            FROM incident i
            JOIN graph_nodes g ON g.person_id = i.neighbor_id
            JOIN persons p ON p.id = i.neighbor_id
            ORDER BY i.shared_works_count DESC, i.collaboration_score DESC, i.neighbor_id
            """,
            [person_id, person_id, person_id, min_shared, limit],
        ).fetchall()

    center_id = str(center[0])
    nodes = [
        {
            "id": center_id,
            "name": center[1],
            "x": 0,
            "y": 0,
            "degree": center[2],
            "visibleWeightedDegree": center[3],
            "nodeSize": center[4],
            "roleLayer": center[5],
            "isCenter": True,
        }
    ]
    edges = []

    for index, row in enumerate(neighbors):
        ring = index // 36
        position = index % 36
        angle = position / 36 * 6.283185307179586 + ring * 0.31
        radius = 180 + ring * 120
        node_id = str(row[0])
        nodes.append(
            {
                "id": node_id,
                "name": row[1],
                "x": round(radius * math.cos(angle), 3),
                "y": round(radius * math.sin(angle), 3),
                "degree": row[2],
                "visibleWeightedDegree": row[3],
                "nodeSize": row[4],
                "roleLayer": row[5],
                "isCenter": False,
            }
        )
        edges.append(
            {
                "source": center_id,
                "target": node_id,
                "w": row[6],
                "collaborationScore": row[7],
                "firstYear": row[8],
                "lastYear": row[9],
                "selectionReason": row[10],
            }
        )

    return {"centerId": center_id, "nodes": nodes, "edges": edges}


@app.get("/api/search/persons")
def search_persons(
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=50000, ge=1, le=50000),
) -> list[dict[str, Any]]:
    with connect_readonly() as conn:
        if q:
            rows = conn.execute(
                """
                SELECT g.person_id::TEXT AS id, p.name, g.visible_degree AS degree
                FROM graph_nodes g
                JOIN persons p ON g.person_id = p.id
                WHERE p.name ILIKE ?
                ORDER BY g.visible_degree DESC, g.visible_weighted_degree DESC, p.name
                LIMIT ?
                """,
                [f"%{q}%", limit],
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT g.person_id::TEXT AS id, p.name, g.visible_degree AS degree
                FROM graph_nodes g
                JOIN persons p ON g.person_id = p.id
                ORDER BY g.visible_degree DESC, g.visible_weighted_degree DESC, p.name
                LIMIT ?
                """,
                [limit],
            ).fetchall()

    return row_dicts(rows, ["id", "name", "degree"])
