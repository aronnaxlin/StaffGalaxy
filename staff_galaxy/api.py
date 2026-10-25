from __future__ import annotations

import hashlib
import json
import math
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from neo4j import Driver
from neo4j.exceptions import AuthError, ServiceUnavailable

from .graph_buffers import VERSION as BUFFERS_VERSION, build_graph_buffers
from .graph_db import connection_uri, get_driver, latest_data_snapshot, read, read_one
from .search_index import (
    compact_search_text,
    extract_person_name_cn,
    extract_person_name_tw,
    normalize_search_text,
)


def graph() -> Driver:
    try:
        return get_driver()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def row_dicts(rows: list[tuple[Any, ...]], columns: list[str]) -> list[dict[str, Any]]:
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _source_payload(driver: Driver) -> dict[str, Any]:
    return {
        "label": "Bangumi Archive · Neo4j",
        "dbPath": connection_uri(),
        "snapshot": latest_data_snapshot(driver),
    }


def _person_payload(person_id: int | str, name: str, infobox: str = "") -> dict[str, Any]:
    return {
        "id": str(person_id),
        "name": name,
        "nameCn": extract_person_name_cn(infobox),
        "nameTw": extract_person_name_tw(infobox),
    }


def _join_roles(roles: list[str]) -> str:
    return "、".join(sorted(role for role in roles if role is not None))


GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))


def _hash_fraction(s: str) -> float:
    """Deterministic float in [0, 1) from a string — stable across restarts."""
    h = hashlib.md5(s.encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFF_FFFF


def _warm_graph_buffers() -> None:
    """Build the galaxy buffers once at startup so the first visitor gets a cache hit."""
    try:
        driver = get_driver()
        _graph_buffers(driver, _graph_cache_key(driver))
    except Exception as exc:  # The API still serves (and reports 503s) without Neo4j.
        print(f"Graph buffer warm-up skipped: {exc}", flush=True)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    threading.Thread(target=_warm_graph_buffers, name="warm-graph-buffers", daemon=True).start()
    yield


app = FastAPI(title="Staff Galaxy API", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
# Meta JSON compresses ~10×; buffers ~2.5×. Both are snapshot-immutable, so the
# per-request gzip CPU cost is paid once per client per snapshot.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(ServiceUnavailable)
@app.exception_handler(AuthError)
async def _neo4j_unavailable(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": f"Neo4j unavailable at {connection_uri()}: {exc}"},
    )


# In-memory buffers cache, keyed by (graph URI, snapshot, layout). A new Archive
# snapshot or layout rebuild changes the key, so stale payloads are never served.
_graph_buffers_cache: dict[tuple[Any, ...], Any] = {}


def _graph_geometry_row(driver: Driver) -> dict[str, Any]:
    return read_one(
        driver,
        """
        MATCH (g:GalaxyNode)
        RETURN count(g) AS nodes,
               coalesce(max(g.layout_method), 'unknown') AS layout_method,
               // Position checksum: changes when a layout rebuild rewrites x/y
               // even if counts and layout_method stay the same.
               round(coalesce(sum(g.x * g.x + g.y * g.y), 0.0), 2) AS fingerprint
        """,
    ) or {"nodes": 0, "layout_method": "unknown", "fingerprint": 0.0}


def _visible_edge_count(driver: Driver) -> int:
    row = read_one(driver, "MATCH ()-[e:COLLAB]->() RETURN count(e) AS edges")
    return int(row["edges"]) if row else 0


def _graph_cache_key(driver: Driver) -> tuple[Any, ...]:
    snapshot = latest_data_snapshot(driver) or {}
    row = _graph_geometry_row(driver)
    return (
        connection_uri(),
        snapshot.get("archiveName"),
        snapshot.get("archiveCreatedAt"),
        row["layout_method"],
        int(row["nodes"]),
        _visible_edge_count(driver),
        float(row["fingerprint"]),
        BUFFERS_VERSION,
    )


def _graph_buffers(driver: Driver, key: tuple[Any, ...]) -> Any:
    cached = _graph_buffers_cache.get(key)
    if cached is None:
        _graph_buffers_cache.clear()
        cached = build_graph_buffers(driver)
        _graph_buffers_cache[key] = cached
    return cached


def _immutable_headers(cache_key: tuple[Any, ...]) -> dict[str, str]:
    # The frontend appends ?v=<archive name> to both URLs, so a new snapshot is a
    # new URL and immutable caching is safe; ETag covers non-URL revalidation.
    token = hashlib.md5(repr(cache_key).encode()).hexdigest()[:16]
    return {
        "ETag": f'"sg-{token}"',
        "Cache-Control": "public, max-age=31536000, immutable",
    }


@app.get("/api/manifest")
def manifest() -> dict[str, Any]:
    driver = graph()
    graph_row = _graph_geometry_row(driver)
    return {
        "version": 2,
        "db_path": connection_uri(),
        "snapshot": latest_data_snapshot(driver),
        "graph": {
            "nodes": int(graph_row["nodes"]),
            "edges": _visible_edge_count(driver),
            "layoutMethod": str(graph_row["layout_method"]),
            # Frontend cache-buster for the immutable buffers/meta URLs.
            "geometryFingerprint": float(graph_row["fingerprint"]),
        },
    }


@app.get("/api/graph/buffers")
def graph_buffers(request: Request) -> Response:
    driver = graph()
    cache_key = _graph_cache_key(driver)
    headers = _immutable_headers(cache_key)
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    buffers = _graph_buffers(driver, cache_key)
    return Response(content=buffers.payload, media_type="application/octet-stream", headers=headers)


@app.get("/api/graph/meta")
def graph_meta(request: Request) -> Response:
    driver = graph()
    cache_key = _graph_cache_key(driver)
    headers = _immutable_headers(cache_key)
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    buffers = _graph_buffers(driver, cache_key)
    snapshot = latest_data_snapshot(driver)
    body = json.dumps({**buffers.meta, "snapshot": snapshot}, ensure_ascii=False)
    return Response(content=body, media_type="application/json", headers=headers)


@app.get("/api/person/{person_id}/galaxy")
def person_galaxy(
    person_id: int,
    limit: Annotated[int, Query(ge=1, le=600)] = 220,
    min_shared: Annotated[int, Query(ge=1, le=1000)] = 1,
) -> dict[str, Any]:
    driver = graph()
    center = read_one(
        driver,
        """
        MATCH (g:GalaxyNode {id: $person_id})
        RETURN g.name AS name, g.infobox AS infobox, g.visible_degree AS degree,
               g.visible_weighted_degree AS weighted_degree, g.node_size AS node_size,
               g.role_layer AS role_layer
        """,
        person_id=person_id,
    )
    if center is None:
        raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

    neighbors = read(
        driver,
        """
        MATCH (:GalaxyNode {id: $person_id})-[e:COLLAB]-(n:GalaxyNode)
        WHERE e.shared_works_count >= $min_shared
        RETURN n.id AS id, n.name AS name, n.infobox AS infobox,
               n.visible_degree AS degree, n.visible_weighted_degree AS weighted_degree,
               n.node_size AS node_size, n.role_layer AS role_layer,
               e.shared_works_count AS shared, e.collaboration_score AS score,
               e.first_year AS first_year, e.last_year AS last_year,
               e.selection_reason AS selection_reason
        ORDER BY shared DESC, score DESC, id
        LIMIT $limit
        """,
        person_id=person_id,
        min_shared=min_shared,
        limit=limit,
    )
    # Highest-weight tier each neighbor held on works shared with the center.
    neighbor_tiers = {
        row["id"]: row["tier"]
        for row in read(
            driver,
            """
            MATCH (:Person {id: $person_id})-[:CREDITED]->(:Anime)<-[r:CREDITED]-(n:Person)
            WHERE n.id IN $neighbor_ids
            WITH n.id AS id, r ORDER BY r.role_weight DESC
            RETURN id, head(collect(r.role_tier)) AS tier
            """,
            person_id=person_id,
            neighbor_ids=[row["id"] for row in neighbors],
        )
    }

    center_id = str(person_id)
    nodes = [
        {
            "id": center_id,
            "name": center["name"],
            "nameCn": extract_person_name_cn(center["infobox"] or ""),
            "nameTw": extract_person_name_tw(center["infobox"] or ""),
            "x": 0,
            "y": 0,
            "degree": center["degree"],
            "visibleWeightedDegree": center["weighted_degree"],
            "nodeSize": center["node_size"],
            "roleLayer": center["role_layer"],
            "isCenter": True,
        }
    ]
    edges = []

    max_shared = neighbors[0]["shared"] if neighbors else 1

    for index, row in enumerate(neighbors):
        node_id = str(row["id"])
        seed = _hash_fraction(node_id)
        shared = row["shared"]

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
                "name": row["name"],
                "nameCn": extract_person_name_cn(row["infobox"] or ""),
                "nameTw": extract_person_name_tw(row["infobox"] or ""),
                "x": round(radius * math.cos(angle), 3),
                "y": round(radius * math.sin(angle), 3),
                "degree": row["degree"],
                "visibleWeightedDegree": row["weighted_degree"],
                "nodeSize": row["node_size"],
                "roleLayer": row["role_layer"],
                "isCenter": False,
                "sharedWorksCount": shared,
                "collaborationScore": round(row["score"], 2),
                "firstYear": row["first_year"],
                "lastYear": row["last_year"],
                "neighborRoleTier": neighbor_tiers.get(row["id"]),
            }
        )
        edges.append(
            {
                "source": center_id,
                "target": node_id,
                "w": shared,
                "collaborationScore": row["score"],
                "firstYear": row["first_year"],
                "lastYear": row["last_year"],
                "selectionReason": row["selection_reason"],
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
    driver = graph()
    person = read_one(
        driver,
        """
        MATCH (p:Person {id: $person_id})
        OPTIONAL MATCH (p)-[c:CREDITED]->(s:Anime)
        RETURN p.name AS name, p.infobox AS infobox, p.career_json AS career_json,
               p.summary AS summary,
               count(c) AS credit_count,
               count(DISTINCT s) AS subject_count,
               count(CASE WHEN c.role_tier = 'S' THEN 1 END) AS tier_s,
               count(CASE WHEN c.role_tier = 'A' THEN 1 END) AS tier_a,
               count(CASE WHEN c.role_tier = 'B' THEN 1 END) AS tier_b,
               count(CASE WHEN c.role_tier = 'C' THEN 1 END) AS tier_c,
               count(CASE WHEN c.role_tier = 'D' THEN 1 END) AS tier_d,
               count(CASE WHEN c.role_tier IN ['E', 'F'] THEN 1 END) AS tier_ef,
               min(s.year) AS first_year,
               max(s.year) AS latest_year
        """,
        person_id=person_id,
    )
    if person is None:
        raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

    role_rows = read(
        driver,
        """
        MATCH (:Person {id: $person_id})-[c:CREDITED]->()
        WITH c.position_id AS position_id, c.position_cn AS position,
             c.normalized_role AS normalized_role, c.role_tier AS role_tier,
             count(*) AS credit_count
        RETURN position, normalized_role, role_tier, credit_count
        ORDER BY credit_count DESC, role_tier, position
        LIMIT $role_limit
        """,
        person_id=person_id,
        role_limit=role_limit,
    )
    recent_rows = read(
        driver,
        """
        MATCH (:Person {id: $person_id})-[c:CREDITED]->(s:Anime)
        WITH s, collect(DISTINCT c.position_cn) AS roles, max(c.role_weight) AS max_role_weight
        RETURN s.id AS subject_id, s.name AS subject_name, s.name_cn AS subject_name_cn,
               s.year AS year, s.date AS date, roles, max_role_weight
        ORDER BY coalesce(s.year, 0) DESC, s.date DESC, max_role_weight DESC, s.id DESC
        LIMIT $recent_limit
        """,
        person_id=person_id,
        recent_limit=recent_limit,
    )

    try:
        career = json.loads(person["career_json"] or "[]")
    except json.JSONDecodeError:
        career = []

    return {
        "person": {
            "id": str(person_id),
            "name": person["name"],
            "nameCn": extract_person_name_cn(person["infobox"] or ""),
            "nameTw": extract_person_name_tw(person["infobox"] or ""),
            "career": career if isinstance(career, list) else [],
            "summary": person["summary"] or "",
        },
        "stats": {
            "animeCreditCount": int(person["credit_count"]),
            "animeSubjectCount": int(person["subject_count"]),
            "tierSCount": int(person["tier_s"]),
            "tierACount": int(person["tier_a"]),
            "tierBCount": int(person["tier_b"]),
            "tierCCount": int(person["tier_c"]),
            "tierDCount": int(person["tier_d"]),
            "tierEFCount": int(person["tier_ef"]),
            "firstCreditYear": person["first_year"],
            "latestCreditYear": person["latest_year"],
        },
        "topRoles": [
            {
                "position": row["position"],
                "normalizedRole": row["normalized_role"],
                "roleTier": row["role_tier"],
                "creditCount": int(row["credit_count"]),
            }
            for row in role_rows
        ],
        "recentWorks": [
            {
                "subjectId": int(row["subject_id"]),
                "subjectName": row["subject_name"],
                "subjectNameCn": row["subject_name_cn"],
                "year": row["year"],
                "date": row["date"],
                "roles": _join_roles(row["roles"]),
                "maxRoleWeight": float(row["max_role_weight"] or 0),
            }
            for row in recent_rows
        ],
        "source": _source_payload(driver),
    }


@app.get("/api/person/{person_id}/credits")
def person_credits(
    person_id: int,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Complete row-level anime credit history for one person."""
    driver = graph()
    person = read_one(
        driver,
        """
        MATCH (p:Person {id: $person_id})
        RETURN p.name AS name, p.infobox AS infobox, COUNT { (p)-[:CREDITED]->() } AS total
        """,
        person_id=person_id,
    )
    if person is None:
        raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

    rows = read(
        driver,
        """
        MATCH (:Person {id: $person_id})-[c:CREDITED]->(s:Anime)
        RETURN s.id AS subject_id, s.name AS subject_name, s.name_cn AS subject_name_cn,
               s.year AS year, s.date AS date, c.position_id AS position_id,
               c.position_cn AS position, c.position_en AS position_en,
               c.raw_position AS raw_position, c.normalized_role AS normalized_role,
               c.role_tier AS role_tier, c.role_weight AS role_weight,
               c.appear_eps AS appear_eps
        ORDER BY coalesce(s.year, 0) DESC, s.date DESC, s.id DESC, c.role_weight DESC, c.position_cn
        SKIP $offset
        LIMIT $limit
        """,
        person_id=person_id,
        offset=offset,
        limit=limit,
    )

    return {
        "person": _person_payload(person_id, person["name"], person["infobox"] or ""),
        "total": int(person["total"]),
        "limit": limit,
        "offset": offset,
        "credits": [
            {
                "subjectId": int(row["subject_id"]),
                "subjectName": row["subject_name"],
                "subjectNameCn": row["subject_name_cn"],
                "year": row["year"],
                "date": row["date"],
                "positionId": row["position_id"],
                "position": row["position"],
                "positionEn": row["position_en"],
                "rawPosition": row["raw_position"],
                "normalizedRole": row["normalized_role"],
                "roleTier": row["role_tier"],
                "roleWeight": float(row["role_weight"] or 0),
                "appearEps": row["appear_eps"] or "",
            }
            for row in rows
        ],
        "source": _source_payload(driver),
    }


@app.get("/api/person/{person_id}/knowledge-graph")
def person_knowledge_graph(
    person_id: int,
    people: Annotated[int, Query(ge=1, le=40)] = 10,
    works: Annotated[int, Query(ge=1, le=60)] = 14,
) -> dict[str, Any]:
    """Local Person-[:CREDITED]->Anime subgraph around one person, for the KG panel.

    Keeps the `people` strongest collaborators (by collaboration score over the
    complete graph) and the `works` anime that connect the center to the most of
    them. Every link is a real CREDITED relationship, labelled with its roles.
    """
    driver = graph()
    center = read_one(
        driver,
        "MATCH (p:Person {id: $person_id}) RETURN p.name AS name, p.infobox AS infobox",
        person_id=person_id,
    )
    if center is None:
        raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

    collaborators = read(
        driver,
        """
        MATCH (:Person {id: $person_id})-[rc:CREDITED]->(a:Anime)<-[ro:CREDITED]-(o:Person)
        WHERE o.id <> $person_id
        WITH o, a, max(rc.role_weight) AS center_weight, max(ro.role_weight) AS other_weight
        WITH o, count(a) AS shared, sum(sqrt(center_weight * other_weight)) AS score
        ORDER BY score DESC, shared DESC, o.id
        LIMIT $people
        RETURN o.id AS id, o.name AS name, o.infobox AS infobox, shared, score
        """,
        person_id=person_id,
        people=people,
    )
    collaborator_ids = [row["id"] for row in collaborators]
    anime_rows = read(
        driver,
        """
        MATCH (c:Person {id: $person_id})-[rc:CREDITED]->(a:Anime)
        OPTIONAL MATCH (a)<-[:CREDITED]-(o:Person) WHERE o.id IN $collaborator_ids
        WITH a, max(rc.role_weight) AS center_weight, count(DISTINCT o) AS linked
        ORDER BY linked DESC, center_weight DESC, coalesce(a.year, 0) DESC, a.id
        LIMIT $works
        RETURN a.id AS id, a.name AS name, a.name_cn AS name_cn, a.year AS year, linked
        """,
        person_id=person_id,
        collaborator_ids=collaborator_ids,
        works=works,
    )
    link_rows = read(
        driver,
        """
        MATCH (p:Person) WHERE p.id IN $person_ids
        MATCH (p)-[r:CREDITED]->(a:Anime) WHERE a.id IN $anime_ids
        WITH p, a, r ORDER BY r.role_weight DESC, r.position_cn
        RETURN p.id AS person_id, a.id AS anime_id,
               collect(DISTINCT r.position_cn) AS roles,
               max(r.role_weight) AS role_weight,
               head(collect(r.role_tier)) AS role_tier
        """,
        person_ids=[person_id, *collaborator_ids],
        anime_ids=[row["id"] for row in anime_rows],
    )

    # Drop collaborators whose shared works all fell outside the kept anime.
    linked_people = {row["person_id"] for row in link_rows}
    nodes: list[dict[str, Any]] = [
        {
            **_person_payload(person_id, center["name"], center["infobox"] or ""),
            "key": f"p:{person_id}",
            "kind": "person",
            "isCenter": True,
        }
    ]
    nodes.extend(
        {
            **_person_payload(row["id"], row["name"], row["infobox"] or ""),
            "key": f"p:{row['id']}",
            "kind": "person",
            "isCenter": False,
            "sharedWorksCount": int(row["shared"]),
            "collaborationScore": round(float(row["score"]), 2),
        }
        for row in collaborators
        if row["id"] in linked_people
    )
    nodes.extend(
        {
            "key": f"a:{row['id']}",
            "kind": "anime",
            "id": str(row["id"]),
            "name": row["name"],
            "nameCn": row["name_cn"] or "",
            "year": row["year"],
        }
        for row in anime_rows
    )
    return {
        "centerId": str(person_id),
        "nodes": nodes,
        "links": [
            {
                "source": f"p:{row['person_id']}",
                "target": f"a:{row['anime_id']}",
                "roles": [role for role in row["roles"] if role],
                "roleTier": row["role_tier"],
                "roleWeight": float(row["role_weight"]),
            }
            for row in link_rows
        ],
    }


# Per-pair evidence derived from the knowledge graph: each shared work counts
# once, weighted by both people's highest-weight role on it.
_PAIR_SHARED_WORKS = """
MATCH (a:Person {id: $person_a})-[ra:CREDITED]->(s:Anime)<-[rb:CREDITED]-(b:Person {id: $person_b})
WITH s, collect(DISTINCT ra.position_cn) AS a_roles, collect(DISTINCT rb.position_cn) AS b_roles,
     max(ra.role_weight) AS a_weight, max(rb.role_weight) AS b_weight
RETURN s.id AS subject_id, s.name AS subject_name, s.name_cn AS subject_name_cn,
       s.year AS year, s.date AS date, a_roles, b_roles, a_weight, b_weight
ORDER BY coalesce(s.year, -1) DESC, s.date DESC
"""

_PAIR_STATS = """
UNWIND $pairs AS pair
MATCH (a:Person {id: pair[0]})-[ra:CREDITED]->(s:Anime)<-[rb:CREDITED]-(b:Person {id: pair[1]})
WITH pair, s, max(ra.role_weight) AS a_weight, max(rb.role_weight) AS b_weight
RETURN pair, count(s) AS shared, sum(sqrt(a_weight * b_weight)) AS score
"""


@app.get("/api/collaboration/{person_a}/{person_b}")
def collaboration_detail(person_a: int, person_b: int) -> dict[str, Any]:
    """Shared works, roles, and years for two people who collaborated."""
    driver = graph()
    rows = [] if person_a == person_b else read(
        driver, _PAIR_SHARED_WORKS, person_a=person_a, person_b=person_b
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No collaboration found between {person_a} and {person_b}",
        )

    people = {
        row["id"]: row
        for row in read(
            driver,
            "MATCH (p:Person) WHERE p.id IN $ids RETURN p.id AS id, p.name AS name, p.infobox AS infobox",
            ids=[person_a, person_b],
        )
    }
    years = [row["year"] for row in rows if row["year"] is not None]
    score = sum(math.sqrt(row["a_weight"] * row["b_weight"]) for row in rows)

    return {
        "personA": _person_payload(person_a, people[person_a]["name"], people[person_a]["infobox"] or ""),
        "personB": _person_payload(person_b, people[person_b]["name"], people[person_b]["infobox"] or ""),
        "sharedWorksCount": len(rows),
        "collaborationScore": round(score, 2),
        "firstYear": min(years) if years else None,
        "lastYear": max(years) if years else None,
        "selectionReason": "all_staff",
        "sharedWorks": [
            {
                "subjectId": int(row["subject_id"]),
                "subjectName": row["subject_name"],
                "subjectNameCn": row["subject_name_cn"],
                "year": row["year"],
                "date": row["date"],
                "personARoles": _join_roles(row["a_roles"]),
                "personBRoles": _join_roles(row["b_roles"]),
            }
            for row in rows
        ],
        "source": _source_payload(driver),
    }


# Upper bound on raw shortest paths enumerated per request. Paths that differ
# only in which anime links two people collapse to one person sequence.
PATH_ENUMERATION_LIMIT = 2_000


@app.get("/api/path/{person_a}/{person_b}")
def shortest_path(
    person_a: int,
    person_b: int,
    max_paths: Annotated[int, Query(ge=1, le=10)] = 5,
    max_depth: Annotated[int, Query(ge=1, le=8)] = 6,
) -> dict[str, Any]:
    """All shortest collaboration paths, traversing Person-[:CREDITED]-Anime in the full graph.

    One collaboration hop is Person -> Anime -> Person, so max_depth people-hops
    is 2 * max_depth relationships. Distinct person sequences are ranked by
    their weakest step, then total collaboration score.
    """
    driver = graph()
    endpoints = {
        row["id"]: row
        for row in read(
            driver,
            """
            MATCH (p:Person) WHERE p.id IN $ids
            RETURN p.id AS id, p.name AS name, p.infobox AS infobox,
                   EXISTS { (p)-[:CREDITED]->() } AS has_credits
            """,
            ids=[person_a, person_b],
        )
    }

    if person_a == person_b:
        person = endpoints.get(person_a)
        if person is None:
            return {"found": False, "reason": f"Unknown person {person_a}"}
        return {
            "found": True,
            "degree": 0,
            "pathCount": 1,
            "people": [_person_payload(person_a, person["name"], person["infobox"] or "")],
            "paths": [{"nodes": [str(person_a)], "steps": []}],
        }

    for person_id in (person_a, person_b):
        if not endpoints.get(person_id, {}).get("has_credits"):
            return {"found": False, "reason": f"Person {person_id} has no complete staff edges"}

    # Quantifier bounds cannot be parameters; max_depth is a validated int.
    path_rows = read(
        driver,
        f"""
        MATCH (a:Person {{id: $person_a}}), (b:Person {{id: $person_b}})
        MATCH p = ALL SHORTEST (a)-[:CREDITED]-{{1,{2 * max_depth}}}(b)
        RETURN [n IN nodes(p) WHERE n:Person | n.id] AS ids
        LIMIT $enumeration_limit
        """,
        person_a=person_a,
        person_b=person_b,
        enumeration_limit=PATH_ENUMERATION_LIMIT,
    )
    sequences = list(dict.fromkeys(tuple(row["ids"]) for row in path_rows))
    if not sequences:
        return {
            "found": False,
            "reason": f"No path found between {person_a} and {person_b} within {max_depth} hops",
        }

    pairs = sorted({pair for seq in sequences for pair in zip(seq, seq[1:])})
    step_stats = {
        tuple(row["pair"]): (int(row["shared"]), float(row["score"]))
        for row in read(driver, _PAIR_STATS, pairs=[list(pair) for pair in pairs])
    }

    def strength(seq: tuple[int, ...]) -> tuple[float, float, tuple[int, ...]]:
        scores = [step_stats[pair][1] for pair in zip(seq, seq[1:])]
        return (-min(scores), -sum(scores), seq)

    best = sorted(sequences, key=strength)[:max_paths]
    all_ids = sorted({person_id for seq in best for person_id in seq})
    people = {
        row["id"]: _person_payload(row["id"], row["name"], row["infobox"] or "")
        for row in read(
            driver,
            "MATCH (p:Person) WHERE p.id IN $ids RETURN p.id AS id, p.name AS name, p.infobox AS infobox",
            ids=all_ids,
        )
    }

    return {
        "found": True,
        "degree": len(best[0]) - 1,
        "pathCount": len(best),
        "people": [
            people.get(pid, {"id": str(pid), "name": f"Person {pid}", "nameCn": "", "nameTw": ""})
            for pid in all_ids
        ],
        "paths": [
            {
                "nodes": [str(pid) for pid in seq],
                "steps": [
                    {
                        "source": str(source),
                        "target": str(target),
                        "sharedWorksCount": step_stats[(source, target)][0],
                        "collaborationScore": round(step_stats[(source, target)][1], 2),
                    }
                    for source, target in zip(seq, seq[1:])
                ],
            }
            for seq in best
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



def _search_row(row: dict[str, Any]) -> tuple[str, str, str, str, int]:
    return (
        str(row["id"]),
        row["name"],
        extract_person_name_cn(row["infobox"] or ""),
        extract_person_name_tw(row["infobox"] or ""),
        row["degree"],
    )


_SEARCH_CANDIDATES = """
UNWIND $norms AS v
MATCH (t:SearchTerm) WHERE t.norm CONTAINS v
RETURN DISTINCT t.person_id AS person_id
UNION
UNWIND $compacts AS v
MATCH (t:SearchTerm) WHERE t.compact CONTAINS v
RETURN DISTINCT t.person_id AS person_id
"""


def _search_person_rows(
    driver: Driver,
    q: str,
    limit: int,
    *,
    exclude_id: int | None = None,
) -> list[tuple[str, str, str, str, int]]:
    """Every whitespace-separated term must match one of the person's SearchTerms;
    rank by the best match (exact 0, prefix 1, contains 2) across all variants."""
    terms = [term.strip() for term in q.split() if term.strip()] or [q]
    candidates: set[int] | None = None
    for term in terms:
        # Each term is a TEXT-index CONTAINS seek; intersecting in Python keeps
        # multi-term AND queries from rescanning the whole graph.
        term_ids = {
            row["person_id"]
            for row in read(
                driver,
                _SEARCH_CANDIDATES,
                norms=_normalized_cjk_variants(term),
                compacts=_compact_cjk_variants(term),
            )
        }
        candidates = term_ids if candidates is None else candidates & term_ids
        if not candidates:
            return []
    assert candidates is not None
    candidates.discard(exclude_id)  # type: ignore[arg-type]

    rows = read(
        driver,
        """
        MATCH (g:GalaxyNode) WHERE g.id IN $candidate_ids
        MATCH (g)-[:HAS_SEARCH_TERM]->(st:SearchTerm)
        WITH g, min(CASE
          WHEN st.norm IN $norms OR st.compact IN $compacts THEN 0
          WHEN any(v IN $norms WHERE st.norm STARTS WITH v)
            OR any(v IN $compacts WHERE st.compact STARTS WITH v) THEN 1
          WHEN any(v IN $norms WHERE st.norm CONTAINS v)
            OR any(v IN $compacts WHERE st.compact CONTAINS v) THEN 2
          ELSE 3
        END) AS match_rank
        RETURN g.id AS id, g.name AS name, g.infobox AS infobox, g.visible_degree AS degree
        ORDER BY match_rank, degree DESC, g.visible_weighted_degree DESC, name
        LIMIT $limit
        """,
        candidate_ids=list(candidates),
        norms=_normalized_cjk_variants(q),
        compacts=_compact_cjk_variants(q),
        limit=limit,
    )
    return [_search_row(row) for row in rows]


def _max_fuzzy_distance(query: str) -> int:
    if len(query) < 3:
        return 0
    return 1 if len(query) < 8 else 2


def _edit_distance(a: str, b: str, max_distance: int) -> int:
    """Optimal-string-alignment distance (adjacent transpositions cost 1), with early exit."""
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1
    before_previous: list[int] = []
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
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                value = min(value, before_previous[j - 2] + 1)
            current.append(value)
            row_min = min(row_min, value)
        if row_min > max_distance:
            return max_distance + 1
        before_previous, previous = previous, current
    return previous[-1]


def _fuzzy_search_person_rows(
    driver: Driver,
    q: str,
    limit: int,
    *,
    exclude_ids: set[str],
) -> list[tuple[str, str, str, str, int]]:
    compact_variants = _compact_cjk_variants(q)
    compact_variants = [variant for variant in compact_variants if variant]
    if not compact_variants:
        return []

    query = min(compact_variants, key=len)
    max_distance = _max_fuzzy_distance(query)
    if max_distance == 0:
        return []

    first_chars = sorted({variant[0] for variant in compact_variants if variant})
    candidates = read(
        driver,
        """
        UNWIND $first_chars AS first_char
        MATCH (st:SearchTerm) WHERE st.compact STARTS WITH first_char
        WITH st WHERE size(st.compact) >= $min_length AND size(st.compact) <= $max_length
        MATCH (g:GalaxyNode {id: st.person_id})
        WHERE NOT g.id IN $exclude_ids
        RETURN g.id AS id, g.name AS name, g.infobox AS infobox,
               g.visible_degree AS degree, g.visible_weighted_degree AS weighted_degree,
               st.compact AS term_compact
        """,
        min_length=max(1, len(query) - max_distance),
        max_length=len(query) + max_distance,
        first_chars=first_chars,
        exclude_ids=[int(person_id) for person_id in exclude_ids],
    )

    best_by_person: dict[str, tuple[int, dict[str, Any]]] = {}
    for row in candidates:
        distance = min(
            _edit_distance(str(row["term_compact"]), variant, max_distance)
            for variant in compact_variants
        )
        if distance > max_distance:
            continue
        person_id = str(row["id"])
        current = best_by_person.get(person_id)
        if current is None or distance < current[0]:
            best_by_person[person_id] = (distance, row)

    ranked = sorted(
        best_by_person.values(),
        key=lambda item: (
            item[0],
            -item[1]["degree"],
            -float(item[1]["weighted_degree"] or 0),
            item[1]["name"],
        ),
    )
    return [_search_row(row) for _, row in ranked[:limit]]


@app.get("/api/search/persons")
def search_persons(
    q: str = Query(default="", min_length=0),
    limit: int = Query(default=20, ge=1, le=50000),
) -> list[dict[str, Any]]:
    """Search people by Bangumi ID, names, CJK variants, and Archive infobox aliases."""
    if not q.strip():
        return []
    driver = graph()
    q = q.strip()

    # Numeric ID → exact match first
    if q.isdigit():
        rows = [
            _search_row(row)
            for row in read(
                driver,
                """
                MATCH (g:GalaxyNode {id: $person_id})
                RETURN g.id AS id, g.name AS name, g.infobox AS infobox, g.visible_degree AS degree
                """,
                person_id=int(q),
            )
        ][:limit]
        remaining = limit - len(rows)
        if remaining > 0:
            rows.extend(_search_person_rows(driver, q, remaining, exclude_id=int(q)))
    else:
        rows = _search_person_rows(driver, q, limit)
        if len(rows) < limit:
            seen_ids = {row[0] for row in rows}
            rows.extend(
                _fuzzy_search_person_rows(
                    driver,
                    q,
                    limit - len(rows),
                    exclude_ids=seen_ids,
                )
            )

    return row_dicts(rows, ["id", "name", "nameCn", "nameTw", "degree"])
