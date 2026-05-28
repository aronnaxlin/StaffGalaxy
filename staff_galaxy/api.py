from __future__ import annotations

import hashlib
import json
import os
import math
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .search_index import compact_search_text, extract_person_name_cn, normalize_search_text


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


def _latest_data_snapshot(conn: duckdb.DuckDBPyConnection) -> dict[str, Any] | None:
    exists = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = 'data_snapshots'
        """
    ).fetchone()[0]
    if not exists:
        return None

    row = conn.execute(
        """
        SELECT
          snapshot_id,
          archive_name,
          archive_created_at,
          archive_size_bytes,
          built_at::TEXT,
          source_url
        FROM data_snapshots
        ORDER BY built_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return {
        "snapshotId": row[0],
        "archiveName": row[1],
        "archiveCreatedAt": row[2],
        "archiveSizeBytes": int(row[3] or 0),
        "builtAt": row[4],
        "sourceUrl": row[5],
    }


def _source_payload(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    return {
        "label": "Bangumi Archive local DuckDB",
        "dbPath": str(get_db_path()),
        "snapshot": _latest_data_snapshot(conn),
    }


def _person_payload(person_id: int | str, name: str, infobox: str = "") -> dict[str, Any]:
    return {
        "id": str(person_id),
        "name": name,
        "nameCn": extract_person_name_cn(infobox),
    }


GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))


def _hash_fraction(s: str) -> float:
    """Deterministic float in [0, 1) from a string — stable across restarts."""
    h = hashlib.md5(s.encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFF_FFFF


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
        snapshot = _latest_data_snapshot(conn)

    return {"version": 1, "db_path": str(get_db_path()), "snapshot": snapshot, "levels": level_counts}


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
              p.infobox,
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

    return [
        {
            "id": row[0],
            "name": row[1],
            "nameCn": extract_person_name_cn(row[2] or ""),
            "x": row[3],
            "y": row[4],
            "degree": row[5],
            "visibleWeightedDegree": row[6],
            "nodeSize": row[7],
            "roleLayer": row[8],
        }
        for row in rows
    ]


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
    limit: Annotated[int, Query(ge=1, le=600)] = 220,
    min_shared: Annotated[int, Query(ge=1, le=1000)] = 1,
) -> dict[str, Any]:
    with connect_readonly() as conn:
        center = conn.execute(
            """
            SELECT
              g.person_id::TEXT AS id,
              p.name,
              p.infobox,
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
              p.infobox,
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
            "nameCn": extract_person_name_cn(center[2] or ""),
            "x": 0,
            "y": 0,
            "degree": center[3],
            "visibleWeightedDegree": center[4],
            "nodeSize": center[5],
            "roleLayer": center[6],
            "isCenter": True,
        }
    ]
    edges = []

    max_shared = neighbors[0][7] if neighbors else 1

    for index, row in enumerate(neighbors):
        node_id = str(row[0])
        seed = _hash_fraction(node_id)
        shared = row[7]

        # Radius driven by collaboration strength: stronger → closer to center.
        # Map shared_works_count to [80, 600] — inner ring for top collaborators.
        strength = shared / max(1, max_shared)
        base_radius = 80 + (1.0 - strength) * 520

        # Angular placement: golden-angle spiral for even spread + spiral-arm modulation.
        base_angle = index * GOLDEN_ANGLE
        arm_count = 5
        arm = int(seed * arm_count)
        arm_offset = arm * 2.0 * math.pi / arm_count
        arm_pull = 0.12 * (1.0 - strength)  # weaker collaborations pulled more into arms
        angle = base_angle + (seed - 0.5) * 0.35 + arm_pull * math.sin(base_angle * 3 + arm_offset)

        # Radial perturbation for organic texture.
        radius = base_radius + (seed - 0.5) * 40

        nodes.append(
            {
                "id": node_id,
                "name": row[1],
                "nameCn": extract_person_name_cn(row[2] or ""),
                "x": round(radius * math.cos(angle), 3),
                "y": round(radius * math.sin(angle), 3),
                "degree": row[3],
                "visibleWeightedDegree": row[4],
                "nodeSize": row[5],
                "roleLayer": row[6],
                "isCenter": False,
                "sharedWorksCount": shared,
                "collaborationScore": round(row[8], 2),
                "firstYear": row[9],
                "lastYear": row[10],
            }
        )
        edges.append(
            {
                "source": center_id,
                "target": node_id,
                "w": shared,
                "collaborationScore": row[8],
                "firstYear": row[9],
                "lastYear": row[10],
                "selectionReason": row[11],
            }
        )

    return {"centerId": center_id, "nodes": nodes, "edges": edges}


@app.get("/api/person/{person_id}/detail")
def person_detail(
    person_id: int,
    role_limit: Annotated[int, Query(ge=1, le=20)] = 8,
    recent_limit: Annotated[int, Query(ge=1, le=30)] = 10,
) -> dict[str, Any]:
    """Person stats, top roles, and recent anime credits for the detail panel."""
    with connect_readonly() as conn:
        person = conn.execute(
            """
            SELECT
              p.id::TEXT AS id,
              p.name,
              p.infobox,
              p.career_json,
              p.summary,
              s.anime_credit_count,
              s.anime_subject_count,
              s.tier_s_credit_count,
              s.tier_a_credit_count,
              s.tier_b_credit_count,
              s.tier_c_credit_count,
              s.tier_d_credit_count,
              s.tier_ef_credit_count,
              s.first_credit_year,
              s.latest_credit_year
            FROM persons p
            LEFT JOIN person_anime_stats s ON s.person_id = p.id
            WHERE p.id = ?
            """,
            [person_id],
        ).fetchone()

        if person is None:
            raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

        role_rows = conn.execute(
            """
            SELECT
              position_cn,
              normalized_role,
              role_tier,
              credit_count
            FROM person_role_counts
            WHERE person_id = ?
            ORDER BY credit_count DESC, role_tier, position_cn
            LIMIT ?
            """,
            [person_id, role_limit],
        ).fetchall()

        recent_rows = conn.execute(
            """
            SELECT
              s.id::INTEGER AS subject_id,
              s.name AS subject_name,
              s.name_cn AS subject_name_cn,
              s.year AS subject_year,
              s.date AS subject_date,
              STRING_AGG(DISTINCT c.position_cn, '、' ORDER BY c.position_cn) AS roles,
              MAX(c.role_weight) AS max_role_weight
            FROM credits c
            JOIN subjects s ON s.id = c.subject_id
            WHERE c.person_id = ?
            GROUP BY s.id, s.name, s.name_cn, s.year, s.date
            ORDER BY COALESCE(s.year, 0) DESC, s.date DESC, max_role_weight DESC, s.id DESC
            LIMIT ?
            """,
            [person_id, recent_limit],
        ).fetchall()
        source = _source_payload(conn)

    career_json = person[3] or "[]"
    try:
        career = json.loads(career_json)
    except json.JSONDecodeError:
        career = []

    return {
        "person": {
            "id": person[0],
            "name": person[1],
            "nameCn": extract_person_name_cn(person[2] or ""),
            "career": career if isinstance(career, list) else [],
            "summary": person[4] or "",
        },
        "stats": {
            "animeCreditCount": int(person[5] or 0),
            "animeSubjectCount": int(person[6] or 0),
            "tierSCount": int(person[7] or 0),
            "tierACount": int(person[8] or 0),
            "tierBCount": int(person[9] or 0),
            "tierCCount": int(person[10] or 0),
            "tierDCount": int(person[11] or 0),
            "tierEFCount": int(person[12] or 0),
            "firstCreditYear": int(person[13]) if person[13] is not None else None,
            "latestCreditYear": int(person[14]) if person[14] is not None else None,
        },
        "topRoles": [
            {
                "position": row[0],
                "normalizedRole": row[1],
                "roleTier": row[2],
                "creditCount": int(row[3]),
            }
            for row in role_rows
        ],
        "recentWorks": [
            {
                "subjectId": int(row[0]),
                "subjectName": row[1],
                "subjectNameCn": row[2],
                "year": row[3],
                "date": row[4],
                "roles": row[5] or "",
                "maxRoleWeight": float(row[6] or 0),
            }
            for row in recent_rows
        ],
        "source": source,
    }


@app.get("/api/person/{person_id}/credits")
def person_credits(
    person_id: int,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Complete row-level anime credit history for one person."""
    with connect_readonly() as conn:
        person = conn.execute(
            "SELECT id::TEXT, name, infobox FROM persons WHERE id = ?",
            [person_id],
        ).fetchone()
        if person is None:
            raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

        total = conn.execute(
            "SELECT COUNT(*) FROM credits WHERE person_id = ?",
            [person_id],
        ).fetchone()[0]

        rows = conn.execute(
            """
            SELECT
              c.subject_id::INTEGER AS subject_id,
              s.name AS subject_name,
              s.name_cn AS subject_name_cn,
              s.year AS subject_year,
              s.date AS subject_date,
              c.position_id::INTEGER AS position_id,
              c.position_cn,
              c.position_en,
              c.raw_position,
              c.normalized_role,
              c.role_tier,
              c.role_weight,
              c.appear_eps
            FROM credits c
            JOIN subjects s ON s.id = c.subject_id
            WHERE c.person_id = ?
            ORDER BY COALESCE(s.year, 0) DESC, s.date DESC, s.id DESC, c.role_weight DESC, c.position_cn
            LIMIT ? OFFSET ?
            """,
            [person_id, limit, offset],
        ).fetchall()
        source = _source_payload(conn)

    return {
        "person": _person_payload(person[0], person[1], person[2] or ""),
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "credits": [
            {
                "subjectId": int(row[0]),
                "subjectName": row[1],
                "subjectNameCn": row[2],
                "year": row[3],
                "date": row[4],
                "positionId": int(row[5]) if row[5] is not None else None,
                "position": row[6],
                "positionEn": row[7],
                "rawPosition": row[8],
                "normalizedRole": row[9],
                "roleTier": row[10],
                "roleWeight": float(row[11] or 0),
                "appearEps": row[12] or "",
            }
            for row in rows
        ],
        "source": source,
    }


@app.get("/api/collaboration/{person_a}/{person_b}")
def collaboration_detail(person_a: int, person_b: int) -> dict[str, Any]:
    """Shared works, roles, and years for two people who collaborated."""
    with connect_readonly() as conn:
        source_person_id = min(person_a, person_b)
        target_person_id = max(person_a, person_b)
        edge = conn.execute(
            """
            SELECT
              shared_works_count,
              collaboration_score,
              first_year,
              last_year,
              role_layer
            FROM person_collaboration_edges
            WHERE source_person_id = ?
              AND target_person_id = ?
            """,
            [source_person_id, target_person_id],
        ).fetchone()

        if edge is None:
            raise HTTPException(
                status_code=404,
                detail=f"No collaboration found between {person_a} and {person_b}",
            )

        shared_works_count = int(edge[0])
        collaboration_score = float(edge[1])
        first_year = int(edge[2]) if edge[2] is not None else None
        last_year = int(edge[3]) if edge[3] is not None else None
        selection_reason = str(edge[4])

        # Get both person names
        p_a = conn.execute(
            "SELECT name, infobox FROM persons WHERE id = ?", [person_a]
        ).fetchone()
        p_b = conn.execute(
            "SELECT name, infobox FROM persons WHERE id = ?", [person_b]
        ).fetchone()

        # Get shared works with individual roles
        shared_works_rows = conn.execute(
            """
            SELECT
              s.id::INTEGER AS subject_id,
              s.name AS subject_name,
              s.name_cn AS subject_name_cn,
              s.year AS subject_year,
              s.date AS subject_date,
              (
                SELECT STRING_AGG(DISTINCT c_a.position_cn, '、' ORDER BY c_a.position_cn)
                FROM credits c_a
                WHERE c_a.subject_id = s.id AND c_a.person_id = ?
              ) AS person_a_roles,
              (
                SELECT STRING_AGG(DISTINCT c_b.position_cn, '、' ORDER BY c_b.position_cn)
                FROM credits c_b
                WHERE c_b.subject_id = s.id AND c_b.person_id = ?
              ) AS person_b_roles
            FROM subjects s
            WHERE EXISTS (
              SELECT 1 FROM credits c1 WHERE c1.subject_id = s.id AND c1.person_id = ?
            )
              AND EXISTS (
                SELECT 1 FROM credits c2 WHERE c2.subject_id = s.id AND c2.person_id = ?
              )
            ORDER BY s.year DESC, s.date DESC
            """,
            [person_a, person_b, person_a, person_b],
        ).fetchall()
        source = _source_payload(conn)

    return {
        "personA": _person_payload(person_a, p_a[0], p_a[1] or "") if p_a else {"id": str(person_a), "name": "?", "nameCn": ""},
        "personB": _person_payload(person_b, p_b[0], p_b[1] or "") if p_b else {"id": str(person_b), "name": "?", "nameCn": ""},
        "sharedWorksCount": shared_works_count,
        "collaborationScore": round(collaboration_score, 2),
        "firstYear": first_year,
        "lastYear": last_year,
        "selectionReason": selection_reason,
        "sharedWorks": [
            {
                "subjectId": int(row[0]),
                "subjectName": row[1],
                "subjectNameCn": row[2],
                "year": row[3],
                "date": row[4],
                "personARoles": row[5] or "",
                "personBRoles": row[6] or "",
            }
            for row in shared_works_rows
        ],
        "source": source,
    }


def _person_has_complete_edges(conn: duckdb.DuckDBPyConnection, person_id: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM person_collaboration_edges
        WHERE source_person_id = ? OR target_person_id = ?
        LIMIT 1
        """,
        [person_id, person_id],
    ).fetchone()
    return row is not None


def _frontier_complete_edges(
    conn: duckdb.DuckDBPyConnection,
    frontier: set[int],
) -> list[tuple[int, int, int, float]]:
    conn.execute("DROP TABLE IF EXISTS path_frontier_nodes")
    conn.execute("CREATE TEMP TABLE path_frontier_nodes(id INTEGER)")
    conn.executemany(
        "INSERT INTO path_frontier_nodes VALUES (?)",
        [(person_id,) for person_id in frontier],
    )
    rows = conn.execute(
        """
        SELECT
          f.id AS current_id,
          e.target_person_id AS neighbor_id,
          e.shared_works_count,
          e.collaboration_score
        FROM path_frontier_nodes f
        JOIN person_collaboration_edges e ON e.source_person_id = f.id
        UNION ALL
        SELECT
          f.id AS current_id,
          e.source_person_id AS neighbor_id,
          e.shared_works_count,
          e.collaboration_score
        FROM path_frontier_nodes f
        JOIN person_collaboration_edges e ON e.target_person_id = f.id
        """
    ).fetchall()
    conn.execute("DROP TABLE IF EXISTS path_frontier_nodes")
    return rows


@app.get("/api/path/{person_a}/{person_b}")
def shortest_path(
    person_a: int,
    person_b: int,
    max_paths: Annotated[int, Query(ge=1, le=10)] = 5,
    max_depth: Annotated[int, Query(ge=1, le=8)] = 6,
) -> dict[str, Any]:
    """All shortest paths through the complete staff collaboration graph."""
    with connect_readonly() as conn:
        edge_count = conn.execute("SELECT COUNT(*) FROM person_collaboration_edges").fetchone()[0]
        if edge_count == 0:
            raise HTTPException(status_code=503, detail="No complete collaboration edges available")

        if person_a == person_b:
            person = conn.execute("SELECT name, infobox FROM persons WHERE id = ?", [person_a]).fetchone()
            if person is None:
                return {"found": False, "reason": f"Unknown person {person_a}"}
            return {
                "found": True,
                "degree": 0,
                "pathCount": 1,
                "people": [_person_payload(person_a, person[0], person[1] or "")],
                "paths": [{"nodes": [str(person_a)], "steps": []}],
            }

        if not _person_has_complete_edges(conn, person_a):
            return {"found": False, "reason": f"Person {person_a} has no complete staff edges"}
        if not _person_has_complete_edges(conn, person_b):
            return {"found": False, "reason": f"Person {person_b} has no complete staff edges"}

        parents: dict[int, list[tuple[int, int, float]]] = defaultdict(list)
        depth: dict[int, int] = {person_a: 0}
        frontier: set[int] = {person_a}
        found_depth: int | None = None

        for cur_depth in range(max_depth):
            rows = _frontier_complete_edges(conn, frontier)
            next_frontier: set[int] = set()

            for current, neighbor, swc, cs in rows:
                current_id = int(current)
                neighbor_id = int(neighbor)
                new_depth = cur_depth + 1

                if neighbor_id not in depth:
                    depth[neighbor_id] = new_depth
                    parents[neighbor_id].append((current_id, int(swc), float(cs)))
                    next_frontier.add(neighbor_id)
                elif depth[neighbor_id] == new_depth:
                    parents[neighbor_id].append((current_id, int(swc), float(cs)))

            if person_b in depth and depth[person_b] == cur_depth + 1:
                found_depth = cur_depth + 1
                break
            if not next_frontier:
                break
            frontier = next_frontier

    if person_b not in parents:
        return {
            "found": False,
            "reason": f"No path found between {person_a} and {person_b} within {max_depth} hops",
        }

    # Backtrack to collect all paths (limit to max_paths)
    all_paths: list[tuple[list[int], list[dict[str, Any]]]] = []

    def backtrack(node: int, path_ids: list[int], steps: list[dict[str, Any]]) -> None:
        if len(all_paths) >= max_paths:
            return
        if node == person_a:
            all_paths.append((list(reversed(path_ids)), list(reversed(steps))))
            return
        for prev, swc, cs in parents[node]:
            backtrack(
                prev,
                path_ids + [prev],
                steps
                + [
                    {
                        "source": str(prev),
                        "target": str(node),
                        "sharedWorksCount": swc,
                        "collaborationScore": round(cs, 2),
                    }
                ],
            )

    backtrack(person_b, [person_b], [])

    # Collect all unique person IDs across all paths
    all_ids: set[int] = {person_a, person_b}
    for path_ids, _ in all_paths:
        all_ids.update(path_ids)

    with connect_readonly() as conn:
        name_rows = conn.execute(
            """
            SELECT id, name, infobox FROM persons
            WHERE id IN ({})
            """.format(",".join("?" for _ in all_ids)),
            list(all_ids),
        ).fetchall()

    people: dict[int, dict[str, Any]] = {
        int(r[0]): _person_payload(r[0], r[1], r[2] or "")
        for r in name_rows
    }

    degree = found_depth if found_depth is not None else depth[person_b]

    return {
        "found": True,
        "degree": degree,
        "pathCount": len(all_paths),
        "people": [
            people.get(pid, {"id": str(pid), "name": f"Person {pid}", "nameCn": ""})
            for pid in sorted(all_ids)
        ],
        "paths": [
            {
                "nodes": [str(pid) for pid in path_ids],
                "steps": steps,
            }
            for path_ids, steps in all_paths
        ],
    }


# Common simplified-Chinese → Japanese-kanji / traditional character variants.
# When a user types simplified Chinese, we also search the Japanese form.
_CJK_MAP: dict[str, str] = {
    # Person-name-relevant pairs (simplified → JP/traditional)
    "宫": "宮", "骏": "駿", "马": "馬", "鸟": "鳥", "龙": "龍", "爱": "愛",
    "门": "門", "电": "電", "话": "話", "画": "絵", "书": "書", "车": "車",
    "风": "風", "东": "東", "为": "為", "乐": "楽", "时": "時", "见": "見",
    "长": "長", "对": "対", "发": "発", "传": "伝", "经": "経", "实": "実",
    "气": "気", "边": "辺", "广": "広", "关": "関", "单": "単", "卖": "売",
    "严": "厳", "图": "図", "团": "団", "压": "圧", "盐": "塩", "处": "処",
    "齐": "斉", "斋": "斎", "樱": "桜", "泽": "沢", "译": "訳", "驿": "駅",
    "庄": "荘", "应": "応", "恋": "恋", "战": "戦", "户": "戸", "才": "才",
    "权": "権", "县": "県", "厅": "庁", "价": "価", "假": "仮", "佛": "仏",
    "惠": "恵", "德": "徳", "涩": "渋", "步": "歩", "晚": "晩", "晓": "暁",
    "条": "条", "来": "来", "杰": "傑", "样": "様", "桥": "橋", "横": "横",
    "欢": "歓", "显": "顕", "赞": "賛", "转": "転", "轻": "軽", "边": "辺",
    "进": "進", "运": "運", "过": "過", "远": "遠", "选": "選", "铃": "鈴",
    "铁": "鉄", "银": "銀", "铜": "銅", "钢": "鋼", "锦": "錦", "镇": "鎮",
    "镜": "鏡", "间": "間", "闻": "聞", "问": "問", "闲": "閑", "润": "潤",
    "滨": "浜", "浅": "浅", "渊": "淵", "满": "満", "溪": "渓", "岛": "島",
    "岩": "岩", "崎": "崎", "野": "野", "郎": "郎", "藤": "藤", "原": "原",
    "田": "田", "山": "山", "川": "川", "村": "村", "林": "林", "森": "森",
    "松": "松", "本": "本", "中": "中", "小": "小", "大": "大", "上": "上",
    "下": "下", "高": "高", "桥": "橋", "吉": "吉", "福": "福", "冈": "岡",
    "荣": "栄", "营": "営", "劳": "労", "胜": "勝", "剑": "剣", "剑": "剣",
    "亚": "亜", "围": "囲", "圆": "円", "缘": "縁", "绘": "絵", "继": "継",
    "绿": "緑", "缘": "縁", "总": "総", "纵": "縦", "练": "練", "线": "線",
    "组": "組", "织": "織", "编": "編", "缘": "縁", "绳": "縄", "红": "紅",
    "纪": "紀", "约": "約", "纯": "純", "纳": "納", "级": "級", "纱": "紗",
    "纸": "紙", "纹": "紋", "纺": "紡", "细": "細", "终": "終", "结": "結",
    "给": "給", "统": "統", "丝": "糸", "经": "経", "综": "綜", "绿": "緑",
    "绪": "緒", "缘": "縁", "缩": "縮", "绩": "績", "缲": "繰",
}


def _expand_cjk_variants(text: str) -> list[str]:
    """Generate all CJK variant combinations of a query string.

    For each character that has a known variant, produce both forms.
    Returns up to 12 variant strings to keep queries bounded.
    """
    variants: list[list[str]] = []
    for ch in text:
        pair = [ch]
        alt = _CJK_MAP.get(ch)
        if alt:
            pair.append(alt)
        variants.append(pair)

    # Cartesian product, capped
    from itertools import product as _product

    result: list[str] = []
    for combo in _product(*variants):
        result.append("".join(combo))
        if len(result) >= 12:
            break
    return result


def _normalized_cjk_variants(text: str) -> list[str]:
    return sorted({
        normalize_search_text(variant)
        for variant in _expand_cjk_variants(text)
        if normalize_search_text(variant)
    })


def _compact_cjk_variants(text: str) -> list[str]:
    return sorted({
        compact_search_text(variant)
        for variant in _expand_cjk_variants(text)
        if compact_search_text(variant)
    })


def _search_match_rank_sql(q: str) -> tuple[str, list[str]]:
    norms = _normalized_cjk_variants(q)
    compacts = _compact_cjk_variants(q)
    exact_clauses: list[str] = []
    prefix_clauses: list[str] = []
    contains_clauses: list[str] = []
    params: list[str] = []

    for norm in norms:
        exact_clauses.append("st.term_norm = ?")
        params.append(norm)
    for compact in compacts:
        exact_clauses.append("st.term_compact = ?")
        params.append(compact)
    for norm in norms:
        prefix_clauses.append("st.term_norm LIKE ?")
        params.append(f"{norm}%")
    for compact in compacts:
        prefix_clauses.append("st.term_compact LIKE ?")
        params.append(f"{compact}%")
    for norm in norms:
        contains_clauses.append("st.term_norm LIKE ?")
        params.append(f"%{norm}%")
    for compact in compacts:
        contains_clauses.append("st.term_compact LIKE ?")
        params.append(f"%{compact}%")

    exact_sql = " OR ".join(exact_clauses) or "FALSE"
    prefix_sql = " OR ".join(prefix_clauses) or "FALSE"
    contains_sql = " OR ".join(contains_clauses) or "FALSE"
    return (
        f"""
        MIN(CASE
          WHEN {exact_sql} THEN 0
          WHEN {prefix_sql} THEN 1
          WHEN {contains_sql} THEN 2
          ELSE 3
        END)
        """,
        params,
    )


def _search_person_rows(
    conn: duckdb.DuckDBPyConnection,
    q: str,
    limit: int,
    *,
    exclude_id: int | None = None,
) -> list[tuple[str, str, str, int]]:
    terms = [term.strip() for term in q.split() if term.strip()] or [q]
    conditions: list[str] = []
    params: list[str | int] = []

    for index, term in enumerate(terms):
        norm_variants = _normalized_cjk_variants(term)
        compact_variants = _compact_cjk_variants(term)
        term_clauses: list[str] = []
        for norm in norm_variants:
            term_clauses.append(f"st{index}.term_norm LIKE ?")
            params.append(f"%{norm}%")
        for compact in compact_variants:
            term_clauses.append(f"st{index}.term_compact LIKE ?")
            params.append(f"%{compact}%")
        conditions.append(
            f"""
            EXISTS (
              SELECT 1
              FROM person_search_terms st{index}
              WHERE st{index}.person_id = g.person_id
                AND ({" OR ".join(term_clauses)})
            )
            """
        )

    if exclude_id is not None:
        conditions.append("g.person_id != ?")
        params.append(exclude_id)

    rank_sql, rank_params = _search_match_rank_sql(q)
    rows = conn.execute(
        f"""
        SELECT
          g.person_id::TEXT AS id,
          p.name,
          p.infobox,
          g.visible_degree AS degree,
          {rank_sql} AS match_rank
        FROM graph_nodes g
        JOIN persons p ON g.person_id = p.id
        JOIN person_search_terms st ON st.person_id = g.person_id
        WHERE {" AND ".join(conditions)}
        GROUP BY g.person_id, p.name, p.infobox, g.visible_degree, g.visible_weighted_degree
        ORDER BY match_rank, g.visible_degree DESC, g.visible_weighted_degree DESC, p.name
        LIMIT ?
        """,
        [*rank_params, *params, limit],
    ).fetchall()
    return [(row[0], row[1], extract_person_name_cn(row[2] or ""), row[3]) for row in rows]


def _max_fuzzy_distance(query: str) -> int:
    if len(query) < 3:
        return 0
    return 1 if len(query) < 8 else 2


def _unicode_edit_distance(a: str, b: str, max_distance: int) -> int:
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        row_min = i
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            value = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + cost,
            )
            current.append(value)
            row_min = min(row_min, value)
        if row_min > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


def _fuzzy_search_person_rows(
    conn: duckdb.DuckDBPyConnection,
    q: str,
    limit: int,
    *,
    exclude_ids: set[str],
) -> list[tuple[str, str, str, int]]:
    compact_variants = _compact_cjk_variants(q)
    compact_variants = [variant for variant in compact_variants if variant]
    if not compact_variants:
        return []

    query = min(compact_variants, key=len)
    max_distance = _max_fuzzy_distance(query)
    if max_distance == 0:
        return []

    min_length = max(1, len(query) - max_distance)
    max_length = len(query) + max_distance
    first_chars = sorted({variant[0] for variant in compact_variants if variant})
    if not first_chars:
        return []

    exclude_clause = ""
    exclude_params: list[str] = []
    if exclude_ids:
        exclude_clause = "AND g.person_id::TEXT NOT IN ({})".format(
            ", ".join("?" for _ in exclude_ids)
        )
        exclude_params = sorted(exclude_ids)

    prefix_sql = " OR ".join("starts_with(st.term_compact, ?)" for _ in first_chars)

    if query.isascii():
        rows = conn.execute(
            f"""
            SELECT
              g.person_id::TEXT AS id,
              p.name,
              p.infobox,
              g.visible_degree AS degree,
              MIN(damerau_levenshtein(st.term_compact, ?)) AS fuzzy_distance
            FROM person_search_terms st
            JOIN graph_nodes g ON g.person_id = st.person_id
            JOIN persons p ON p.id = st.person_id
            WHERE st.term_compact <> ''
              AND length(st.term_compact) BETWEEN ? AND ?
              AND ({prefix_sql})
              {exclude_clause}
            GROUP BY g.person_id, p.name, p.infobox, g.visible_degree, g.visible_weighted_degree
            HAVING fuzzy_distance <= ?
            ORDER BY fuzzy_distance, g.visible_degree DESC, g.visible_weighted_degree DESC, p.name
            LIMIT ?
            """,
            [query, min_length, max_length, *first_chars, *exclude_params, max_distance, limit],
        ).fetchall()
        return [(row[0], row[1], extract_person_name_cn(row[2] or ""), row[3]) for row in rows]

    candidates = conn.execute(
        f"""
        SELECT
          g.person_id::TEXT AS id,
          p.name,
          p.infobox,
          g.visible_degree AS degree,
          g.visible_weighted_degree,
          st.term_compact
        FROM person_search_terms st
        JOIN graph_nodes g ON g.person_id = st.person_id
        JOIN persons p ON p.id = st.person_id
        WHERE st.term_compact <> ''
          AND length(st.term_compact) BETWEEN ? AND ?
          AND ({prefix_sql})
          {exclude_clause}
        """,
        [min_length, max_length, *first_chars, *exclude_params],
    ).fetchall()

    best_by_person: dict[str, tuple[int, str, str, int, float]] = {}
    for person_id, name, infobox, degree, weighted_degree, term_compact in candidates:
        distance = min(
            _unicode_edit_distance(str(term_compact), variant, max_distance)
            for variant in compact_variants
        )
        if distance > max_distance:
            continue
        current = best_by_person.get(str(person_id))
        if current is None or distance < current[0]:
            best_by_person[str(person_id)] = (
                distance,
                str(name),
                extract_person_name_cn(str(infobox or "")),
                int(degree),
                float(weighted_degree or 0),
            )

    ranked = sorted(
        best_by_person.items(),
        key=lambda item: (item[1][0], -item[1][3], -item[1][4], item[1][1]),
    )
    return [
        (person_id, name, name_cn, degree)
        for person_id, (_distance, name, name_cn, degree, _weighted_degree) in ranked[:limit]
    ]


@app.get("/api/search/persons")
def search_persons(
    q: str = Query(default="", min_length=0),
    limit: int = Query(default=20, ge=1, le=50000),
) -> list[dict[str, Any]]:
    """Search people by Bangumi ID, names, CJK variants, and Archive infobox aliases."""
    with connect_readonly() as conn:
        if not q.strip():
            return []

        q = q.strip()

        # Numeric ID → exact match first
        if q.isdigit():
            exact_rows = conn.execute(
                """
                SELECT g.person_id::TEXT AS id, p.name, p.infobox, g.visible_degree AS degree
                FROM graph_nodes g
                JOIN persons p ON g.person_id = p.id
                WHERE g.person_id = ?
                LIMIT ?
                """,
                [int(q), limit],
            ).fetchall()
            rows = [(row[0], row[1], extract_person_name_cn(row[2] or ""), row[3]) for row in exact_rows]
            remaining = limit - len(rows)
            if remaining > 0:
                rows.extend(
                    _search_person_rows(conn, q, remaining, exclude_id=int(q))
                )
        else:
            rows = _search_person_rows(conn, q, limit)
            if len(rows) < limit:
                seen_ids = {row[0] for row in rows}
                rows.extend(
                    _fuzzy_search_person_rows(
                        conn,
                        q,
                        limit - len(rows),
                        exclude_ids=seen_ids,
                    )
                )

    return row_dicts(rows, ["id", "name", "nameCn", "degree"])
