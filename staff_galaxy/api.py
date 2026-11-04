from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from scipy.sparse import csgraph

from .graph_buffers import VERSION as BUFFERS_VERSION
from .search_index import compact_search_text, normalize_search_text
from .store import Store, get_store


def store() -> Store:
    try:
        return get_store()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def row_dicts(rows: list[tuple[Any, ...]], columns: list[str]) -> list[dict[str, Any]]:
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _id_list(ids: Iterable[int]) -> str:
    """Bind a list of ids as one parameter: `x IN (SELECT value FROM json_each(?))`."""
    return json.dumps([int(i) for i in ids])


def _source_payload(st: Store) -> dict[str, Any]:
    return {
        "label": "Bangumi Archive",
        "dbPath": st.path.name,
        "snapshot": st.snapshot,
    }


def _person_payload(person_id: int | str, row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(person_id),
        "name": row["name"],
        "nameCn": row["name_cn"],
        "nameTw": row["name_tw"],
    }


def _people(st: Store, ids: Iterable[int]) -> dict[int, sqlite3.Row]:
    return {
        row["id"]: row
        for row in st.read(
            "SELECT id, name, name_cn, name_tw FROM person WHERE id IN (SELECT value FROM json_each(?))",
            (_id_list(ids),),
        )
    }


def _join_roles(roles_json: str) -> str:
    return "、".join(sorted(role for role in json.loads(roles_json) if role is not None))


# NSFW anime stay in the store but are hidden unless a request opts in; the
# galaxy itself (layout, backbone edges) is built from every work.
NsfwParam = Annotated[bool, Query(description="Include NSFW anime as evidence")]

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))


def _hash_fraction(s: str) -> float:
    """Deterministic float in [0, 1) from a string — stable across restarts."""
    h = hashlib.md5(s.encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFF_FFFF


def _warm_store() -> None:
    """Open the store and build the path graph once, so the first visitor gets neither cost."""
    try:
        get_store().path_graph()
    except Exception as exc:  # The API still serves (and reports 503s) without a store.
        print(f"Store warm-up skipped: {exc}", flush=True)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    threading.Thread(target=_warm_store, name="warm-store", daemon=True).start()
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

# Every response is a pure function of the store, which only changes on a
# redeploy: browsers revalidate after 10 minutes, a CDN keeps answers for a day
# (purge it when a new store is deployed).
API_CACHE_CONTROL = "public, max-age=600, s-maxage=86400"


@app.middleware("http")
async def _cache_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    if request.method == "GET" and response.status_code == 200:
        response.headers.setdefault("Cache-Control", API_CACHE_CONTROL)
    return response


def _immutable_headers(st: Store) -> dict[str, str]:
    # The frontend appends ?v=<archive name + geometry fingerprint> to both URLs,
    # so a new snapshot is a new URL and immutable caching is safe; ETag covers
    # non-URL revalidation.
    snapshot = st.snapshot or {}
    key = (
        snapshot.get("archiveName"),
        snapshot.get("archiveCreatedAt"),
        tuple(sorted(st.graph_info.items())),
        BUFFERS_VERSION,
    )
    token = hashlib.md5(repr(key).encode()).hexdigest()[:16]
    return {
        "ETag": f'"sg-{token}"',
        "Cache-Control": "public, max-age=31536000, immutable",
    }


@app.get("/api/manifest")
def manifest() -> dict[str, Any]:
    st = store()
    return {
        "version": 2,
        "db_path": st.path.name,
        "snapshot": st.snapshot,
        "graph": st.graph_info,
    }


@app.get("/api/graph/buffers")
def graph_buffers(request: Request) -> Response:
    st = store()
    headers = _immutable_headers(st)
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    return Response(content=st.graph_buffers, media_type="application/octet-stream", headers=headers)


@app.get("/api/graph/meta")
def graph_meta(request: Request) -> Response:
    st = store()
    headers = _immutable_headers(st)
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    return Response(content=st.graph_meta, media_type="application/json", headers=headers)


@app.get("/api/graph/communities")
def graph_communities() -> Response:
    """Labelled communities and sub-communities, largest first (see communities.py)."""
    return Response(content=store().community_labels, media_type="application/json")


@app.get("/api/graph/featured")
def graph_featured() -> Response:
    """Galaxy node ids shown as avatars, highest priority first (see featured.py)."""
    return Response(content=store().featured_people, media_type="application/json")


@app.get("/api/person/{person_id}/galaxy")
def person_galaxy(
    person_id: int,
    limit: Annotated[int, Query(ge=1, le=600)] = 220,
    min_shared: Annotated[int, Query(ge=1, le=1000)] = 1,
    nsfw: NsfwParam = False,
) -> dict[str, Any]:
    st = store()
    center = st.read_one(
        """
        SELECT p.name, p.name_cn, p.name_tw, g.degree, g.weighted_degree, g.node_size, g.role_layer
        FROM galaxy_node g JOIN person p ON p.id = g.id
        WHERE g.id = ?
        """,
        (person_id,),
    )
    if center is None:
        raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

    neighbors = st.read(
        """
        SELECT n.id, p.name, p.name_cn, p.name_tw, n.degree, n.weighted_degree, n.node_size,
               n.role_layer, e.shared, e.score, e.first_year, e.last_year, e.selection_reason
        FROM (
            SELECT target AS other, shared, score, first_year, last_year, selection_reason
            FROM collab WHERE source = :id
            UNION ALL
            SELECT source, shared, score, first_year, last_year, selection_reason
            FROM collab WHERE target = :id
        ) e
        JOIN galaxy_node n ON n.id = e.other
        JOIN person p ON p.id = n.id
        WHERE e.shared >= :min_shared
        ORDER BY e.shared DESC, e.score DESC, n.id
        LIMIT :limit
        """,
        {"id": person_id, "min_shared": min_shared, "limit": limit},
    )
    # Highest-weight tier each neighbor held on works shared with the center.
    neighbor_tiers: dict[int, str] = {}
    for row in st.read(
        """
        SELECT person_id, role_tier FROM credit
        WHERE person_id IN (SELECT value FROM json_each(?))
          AND anime_id IN (SELECT anime_id FROM credit WHERE person_id = ?)
          AND (? OR NOT nsfw)
        ORDER BY role_weight DESC
        """,
        (_id_list(row["id"] for row in neighbors), person_id, nsfw),
    ):
        neighbor_tiers.setdefault(row["person_id"], row["role_tier"])

    center_id = str(person_id)
    nodes = [
        {
            "id": center_id,
            "name": center["name"],
            "nameCn": center["name_cn"],
            "nameTw": center["name_tw"],
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
                "nameCn": row["name_cn"],
                "nameTw": row["name_tw"],
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
    nsfw: NsfwParam = False,
) -> dict[str, Any]:
    """Person stats, top roles, and recent anime credits for the detail panel."""
    st = store()
    person = st.read_one(
        "SELECT name, name_cn, name_tw, career_json, summary FROM person WHERE id = ?",
        (person_id,),
    )
    if person is None:
        raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

    stats = st.read_one(
        """
        SELECT count(*) AS credit_count,
               count(DISTINCT c.anime_id) AS subject_count,
               count(*) FILTER (WHERE c.role_tier = 'S') AS tier_s,
               count(*) FILTER (WHERE c.role_tier = 'A') AS tier_a,
               count(*) FILTER (WHERE c.role_tier = 'B') AS tier_b,
               count(*) FILTER (WHERE c.role_tier = 'C') AS tier_c,
               count(*) FILTER (WHERE c.role_tier = 'D') AS tier_d,
               count(*) FILTER (WHERE c.role_tier IN ('E', 'F')) AS tier_ef,
               min(a.year) AS first_year,
               max(a.year) AS latest_year
        FROM credit c JOIN anime a ON a.id = c.anime_id
        WHERE c.person_id = ? AND (? OR NOT c.nsfw)
        """,
        (person_id, nsfw),
    )
    assert stats is not None
    role_rows = st.read(
        """
        SELECT position_cn AS position, normalized_role, role_tier, count(*) AS credit_count
        FROM credit WHERE person_id = ? AND (? OR NOT nsfw)
        GROUP BY position_id, position_cn, normalized_role, role_tier
        ORDER BY credit_count DESC, role_tier, position
        LIMIT ?
        """,
        (person_id, nsfw, role_limit),
    )
    recent_rows = st.read(
        """
        SELECT a.id AS subject_id, a.name AS subject_name, a.name_cn AS subject_name_cn,
               a.year, a.date, json_group_array(DISTINCT c.position_cn) AS roles,
               max(c.role_weight) AS max_role_weight
        FROM credit c JOIN anime a ON a.id = c.anime_id
        WHERE c.person_id = ? AND (? OR NOT c.nsfw)
        GROUP BY a.id
        ORDER BY coalesce(a.year, 0) DESC, a.date DESC, max_role_weight DESC, a.id DESC
        LIMIT ?
        """,
        (person_id, nsfw, recent_limit),
    )

    try:
        career = json.loads(person["career_json"] or "[]")
    except json.JSONDecodeError:
        career = []

    return {
        "person": {
            **_person_payload(person_id, person),
            "career": career if isinstance(career, list) else [],
            "summary": person["summary"],
        },
        "stats": {
            "animeCreditCount": int(stats["credit_count"]),
            "animeSubjectCount": int(stats["subject_count"]),
            "tierSCount": int(stats["tier_s"]),
            "tierACount": int(stats["tier_a"]),
            "tierBCount": int(stats["tier_b"]),
            "tierCCount": int(stats["tier_c"]),
            "tierDCount": int(stats["tier_d"]),
            "tierEFCount": int(stats["tier_ef"]),
            "firstCreditYear": stats["first_year"],
            "latestCreditYear": stats["latest_year"],
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
        "source": _source_payload(st),
    }


@app.get("/api/person/{person_id}/credits")
def person_credits(
    person_id: int,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
    nsfw: NsfwParam = False,
) -> dict[str, Any]:
    """Complete row-level anime credit history for one person."""
    st = store()
    person = st.read_one(
        """
        SELECT name, name_cn, name_tw,
               (SELECT count(*) FROM credit WHERE person_id = person.id AND (? OR NOT nsfw)) AS total
        FROM person WHERE id = ?
        """,
        (nsfw, person_id),
    )
    if person is None:
        raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

    rows = st.read(
        """
        SELECT a.id AS subject_id, a.name AS subject_name, a.name_cn AS subject_name_cn,
               a.year, a.date, c.position_id, c.position_cn AS position, c.position_en,
               c.raw_position, c.normalized_role, c.role_tier, c.role_weight, c.appear_eps
        FROM credit c JOIN anime a ON a.id = c.anime_id
        WHERE c.person_id = ? AND (? OR NOT c.nsfw)
        ORDER BY coalesce(a.year, 0) DESC, a.date DESC, a.id DESC, c.role_weight DESC, c.position_cn
        LIMIT ? OFFSET ?
        """,
        (person_id, nsfw, limit, offset),
    )

    return {
        "person": _person_payload(person_id, person),
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
        "source": _source_payload(st),
    }


@app.get("/api/person/{person_id}/knowledge-graph")
def person_knowledge_graph(
    person_id: int,
    people: Annotated[int, Query(ge=1, le=40)] = 10,
    works: Annotated[int, Query(ge=1, le=60)] = 14,
    nsfw: NsfwParam = False,
) -> dict[str, Any]:
    """Local Person-[:CREDITED]->Anime subgraph around one person, for the KG panel.

    Keeps the `people` strongest collaborators (by collaboration score over the
    complete graph) and the `works` anime that connect the center to the most of
    them. Every link is a real CREDITED relationship, labelled with its roles.
    """
    st = store()
    center = st.read_one("SELECT name, name_cn, name_tw FROM person WHERE id = ?", (person_id,))
    if center is None:
        raise HTTPException(status_code=404, detail=f"Unknown person id: {person_id}")

    collaborators = st.read(
        """
        WITH mine AS (
            SELECT anime_id, max(role_weight) AS w FROM credit
            WHERE person_id = :id AND (:nsfw OR NOT nsfw) GROUP BY anime_id
        ),
        theirs AS (
            SELECT c.person_id, c.anime_id, max(c.role_weight) AS w
            FROM credit c JOIN mine USING (anime_id)
            WHERE c.person_id <> :id
            GROUP BY c.person_id, c.anime_id
        )
        SELECT p.id, p.name, p.name_cn, p.name_tw,
               count(*) AS shared, sum(sqrt(mine.w * theirs.w)) AS score
        FROM theirs JOIN mine USING (anime_id) JOIN person p ON p.id = theirs.person_id
        GROUP BY p.id
        ORDER BY score DESC, shared DESC, p.id
        LIMIT :people
        """,
        {"id": person_id, "nsfw": nsfw, "people": people},
    )
    collaborator_ids = _id_list(row["id"] for row in collaborators)
    anime_rows = st.read(
        """
        WITH mine AS (
            SELECT anime_id, max(role_weight) AS w FROM credit
            WHERE person_id = :id AND (:nsfw OR NOT nsfw) GROUP BY anime_id
        )
        SELECT a.id, a.name, a.name_cn, a.year,
               (SELECT count(DISTINCT o.person_id) FROM credit o
                WHERE o.anime_id = a.id
                  AND o.person_id IN (SELECT value FROM json_each(:collaborators))) AS linked
        FROM mine JOIN anime a ON a.id = mine.anime_id
        ORDER BY linked DESC, mine.w DESC, coalesce(a.year, 0) DESC, a.id
        LIMIT :works
        """,
        {"id": person_id, "nsfw": nsfw, "collaborators": collaborator_ids, "works": works},
    )
    # One link per (person, anime): roles in role-weight order, tier of the top role.
    links: dict[tuple[int, int], dict[str, Any]] = {}
    for row in st.read(
        """
        SELECT person_id, anime_id, position_cn, role_weight, role_tier FROM credit
        WHERE person_id IN (SELECT value FROM json_each(?))
          AND anime_id IN (SELECT value FROM json_each(?))
        ORDER BY role_weight DESC, position_cn
        """,
        (
            _id_list([person_id, *(row["id"] for row in collaborators)]),
            _id_list(row["id"] for row in anime_rows),
        ),
    ):
        link = links.setdefault(
            (row["person_id"], row["anime_id"]),
            {"roles": [], "roleTier": row["role_tier"], "roleWeight": float(row["role_weight"])},
        )
        if row["position_cn"] and row["position_cn"] not in link["roles"]:
            link["roles"].append(row["position_cn"])

    # Drop collaborators whose shared works all fell outside the kept anime.
    linked_people = {person for person, _ in links}
    nodes: list[dict[str, Any]] = [
        {
            **_person_payload(person_id, center),
            "key": f"p:{person_id}",
            "kind": "person",
            "isCenter": True,
        }
    ]
    nodes.extend(
        {
            **_person_payload(row["id"], row),
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
            "nameCn": row["name_cn"],
            "year": row["year"],
        }
        for row in anime_rows
    )
    return {
        "centerId": str(person_id),
        "nodes": nodes,
        "links": [
            {"source": f"p:{person}", "target": f"a:{anime}", **link}
            for (person, anime), link in links.items()
        ],
    }


# Per-pair evidence derived from the complete credit table: each shared work
# counts once, weighted by both people's highest-weight role on it.
_PAIR_SHARED_WORKS = """
WITH a AS (
    SELECT anime_id, json_group_array(DISTINCT position_cn) AS roles, max(role_weight) AS w
    FROM credit WHERE person_id = ? AND (? OR NOT nsfw) GROUP BY anime_id
),
b AS (
    SELECT anime_id, json_group_array(DISTINCT position_cn) AS roles, max(role_weight) AS w
    FROM credit WHERE person_id = ? AND (? OR NOT nsfw) GROUP BY anime_id
)
SELECT s.id AS subject_id, s.name AS subject_name, s.name_cn AS subject_name_cn, s.year, s.date,
       a.roles AS a_roles, b.roles AS b_roles, a.w AS a_weight, b.w AS b_weight
FROM a JOIN b USING (anime_id) JOIN anime s ON s.id = anime_id
ORDER BY coalesce(s.year, -1) DESC, s.date DESC, s.id DESC
"""


@app.get("/api/collaboration/{person_a}/{person_b}")
def collaboration_detail(person_a: int, person_b: int, nsfw: NsfwParam = False) -> dict[str, Any]:
    """Shared works, roles, and years for two people who collaborated."""
    st = store()
    rows = [] if person_a == person_b else st.read(_PAIR_SHARED_WORKS, (person_a, nsfw, person_b, nsfw))
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No collaboration found between {person_a} and {person_b}",
        )

    people = _people(st, [person_a, person_b])
    years = [row["year"] for row in rows if row["year"] is not None]
    score = sum(math.sqrt(row["a_weight"] * row["b_weight"]) for row in rows)

    return {
        "personA": _person_payload(person_a, people[person_a]),
        "personB": _person_payload(person_b, people[person_b]),
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
        "source": _source_payload(st),
    }


# Upper bound on distinct shortest person sequences enumerated per request.
PATH_ENUMERATION_LIMIT = 2_000


def _shortest_sequences(
    st: Store, a: int, b: int, max_depth: int, nsfw: bool
) -> list[tuple[int, ...]]:
    """Distinct person-index sequences of every shortest a→b path (capped).

    Distances come from a BFS over the bipartite Person–Anime graph (one
    collaboration hop is two edges). A person is on a shortest path iff
    dist_a + dist_b equals the a→b distance; the DFS walks those layers,
    expanding the strongest direct link first so the cap keeps strong paths.
    """
    graph = st.path_graph(nsfw)
    pa, ap = graph.person_anime, graph.anime_person
    person_count = len(graph.person_ids)
    dist = csgraph.dijkstra(
        graph.adjacency, directed=True, indices=[a, b], unweighted=True, limit=2 * max_depth
    )
    total = dist[0, b]
    if not math.isfinite(total):
        return []
    da, db, total = dist[0], dist[1], int(total)
    hops = total // 2

    children_cache: dict[int, np.ndarray] = {}

    def children(u: int, k: int) -> np.ndarray:
        cached = children_cache.get(u)
        if cached is not None:
            return cached
        lo, hi = pa.indptr[u], pa.indptr[u + 1]
        anime, weights = pa.indices[lo:hi], pa.data[lo:hi]
        keep = (da[person_count + anime] == 2 * k + 1) & (db[person_count + anime] == total - 2 * k - 1)
        people: list[np.ndarray] = []
        scores: list[np.ndarray] = []
        for x, w in zip(anime[keep], weights[keep]):
            lo, hi = ap.indptr[x], ap.indptr[x + 1]
            members = ap.indices[lo:hi]
            on_path = (da[members] == 2 * k + 2) & (db[members] == total - 2 * k - 2)
            people.append(members[on_path])
            scores.append(np.sqrt(w * ap.data[lo:hi][on_path]))
        if not people:
            result = np.empty(0, dtype=np.int64)
        else:
            vs, ss = np.concatenate(people), np.concatenate(scores)
            order = np.lexsort((-ss, vs))  # by person, strongest link first
            vs, ss = vs[order], ss[order]
            uniq, first = np.unique(vs, return_index=True)
            best = ss[first]
            result = uniq[np.lexsort((uniq, -best))]
        children_cache[u] = result
        return result

    sequences: list[tuple[int, ...]] = []

    def extend(prefix: list[int]) -> None:
        k = len(prefix) - 1
        if k == hops:
            sequences.append(tuple(prefix))
            return
        for v in children(prefix[-1], k):
            if len(sequences) >= PATH_ENUMERATION_LIMIT:
                return
            extend([*prefix, int(v)])

    extend([a])
    return sequences


@app.get("/api/path/{person_a}/{person_b}")
def shortest_path(
    person_a: int,
    person_b: int,
    max_paths: Annotated[int, Query(ge=1, le=10)] = 5,
    max_depth: Annotated[int, Query(ge=1, le=8)] = 6,
    nsfw: NsfwParam = False,
) -> dict[str, Any]:
    """All shortest collaboration paths through Person–Anime credits in the full graph.

    One collaboration hop is Person -> Anime -> Person. Paths that differ only
    in the linking anime collapse to one person sequence; sequences are ranked
    by their weakest step, then total collaboration score.
    """
    st = store()
    if person_a == person_b:
        person = _people(st, [person_a]).get(person_a)
        if person is None:
            return {"found": False, "reason": f"Unknown person {person_a}"}
        return {
            "found": True,
            "degree": 0,
            "pathCount": 1,
            "people": [_person_payload(person_a, person)],
            "paths": [{"nodes": [str(person_a)], "steps": []}],
        }

    graph = st.path_graph(nsfw)
    index_a, index_b = graph.index_of(person_a), graph.index_of(person_b)
    for person_id, index in ((person_a, index_a), (person_b, index_b)):
        if index is None:
            return {"found": False, "reason": f"Person {person_id} has no complete staff edges"}
    assert index_a is not None and index_b is not None

    sequences = [
        tuple(int(graph.person_ids[i]) for i in seq)
        for seq in _shortest_sequences(st, index_a, index_b, max_depth, nsfw)
    ]
    if not sequences:
        return {
            "found": False,
            "reason": f"No path found between {person_a} and {person_b} within {max_depth} hops",
        }

    pairs = {pair for seq in sequences for pair in zip(seq, seq[1:])}
    step_stats = {
        (s, t): graph.pair_stats(graph.index_of(s), graph.index_of(t))  # type: ignore[arg-type]
        for s, t in pairs
    }

    def strength(seq: tuple[int, ...]) -> tuple[float, float, tuple[int, ...]]:
        scores = [step_stats[pair][1] for pair in zip(seq, seq[1:])]
        return (-min(scores), -sum(scores), seq)

    best = sorted(sequences, key=strength)[:max_paths]
    all_ids = sorted({person_id for seq in best for person_id in seq})
    people = _people(st, all_ids)

    return {
        "found": True,
        "degree": len(best[0]) - 1,
        "pathCount": len(best),
        "people": [
            _person_payload(pid, people[pid])
            if pid in people
            else {"id": str(pid), "name": f"Person {pid}", "nameCn": "", "nameTw": ""}
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



SearchRow = tuple[str, str, str, str, int]

_SEARCH_COLUMNS = """
st.person_id, st.norm, st.compact, g.degree, g.weighted_degree, p.name, p.name_cn, p.name_tw
FROM search_term st
JOIN galaxy_node g ON g.id = st.person_id
JOIN person p ON p.id = st.person_id
"""


def _search_row(row: sqlite3.Row) -> SearchRow:
    return (str(row["person_id"]), row["name"], row["name_cn"], row["name_tw"], row["degree"])


def _search_candidates(st: Store, norms: list[str], compacts: list[str]) -> set[int]:
    """People with any search term containing any variant (one scan over search_term)."""
    conditions = ["instr(norm, ?) > 0"] * len(norms) + ["instr(compact, ?) > 0"] * len(compacts)
    if not conditions:
        return set()
    return {
        row[0]
        for row in st.read(
            f"SELECT DISTINCT person_id FROM search_term WHERE {' OR '.join(conditions)}",
            (*norms, *compacts),
        )
    }


def _search_person_rows(
    st: Store,
    q: str,
    limit: int,
    *,
    exclude_id: int | None = None,
) -> list[SearchRow]:
    """Every whitespace-separated term must match one of the person's search terms;
    rank by the best match (exact 0, prefix 1, contains 2) across all variants."""
    terms = [term.strip() for term in q.split() if term.strip()] or [q]
    candidates: set[int] | None = None
    for term in terms:
        term_ids = _search_candidates(st, _normalized_cjk_variants(term), _compact_cjk_variants(term))
        candidates = term_ids if candidates is None else candidates & term_ids
        if not candidates:
            return []
    assert candidates is not None
    candidates.discard(exclude_id)  # type: ignore[arg-type]

    norms, compacts = _normalized_cjk_variants(q), _compact_cjk_variants(q)
    norm_set, compact_set = set(norms), set(compacts)

    def match_rank(norm: str, compact: str) -> int:
        if norm in norm_set or compact in compact_set:
            return 0
        if any(norm.startswith(v) for v in norms) or any(compact.startswith(v) for v in compacts):
            return 1
        if any(v in norm for v in norms) or any(v in compact for v in compacts):
            return 2
        return 3

    best: dict[int, tuple[int, sqlite3.Row]] = {}
    for row in st.read(
        f"SELECT {_SEARCH_COLUMNS} WHERE st.person_id IN (SELECT value FROM json_each(?))",
        (_id_list(candidates),),
    ):
        rank = match_rank(row["norm"], row["compact"])
        current = best.get(row["person_id"])
        if current is None or rank < current[0]:
            best[row["person_id"]] = (rank, row)

    ranked = sorted(
        best.values(),
        key=lambda item: (item[0], -item[1]["degree"], -item[1]["weighted_degree"], item[1]["name"]),
    )
    return [_search_row(row) for _, row in ranked[:limit]]


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
    st: Store,
    q: str,
    limit: int,
    *,
    exclude_ids: set[str],
) -> list[SearchRow]:
    compact_variants = _compact_cjk_variants(q)
    compact_variants = [variant for variant in compact_variants if variant]
    if not compact_variants:
        return []

    query = min(compact_variants, key=len)
    max_distance = _max_fuzzy_distance(query)
    if max_distance == 0:
        return []

    min_length, max_length = max(1, len(query) - max_distance), len(query) + max_distance
    candidates: list[sqlite3.Row] = []
    for first_char in sorted({variant[0] for variant in compact_variants}):
        # Prefix range on the compact index: [c, next code point).
        candidates.extend(
            st.read(
                f"""
                SELECT {_SEARCH_COLUMNS}
                WHERE st.compact >= ? AND st.compact < ? AND length(st.compact) BETWEEN ? AND ?
                """,
                (first_char, chr(ord(first_char) + 1), min_length, max_length),
            )
        )

    best_by_person: dict[str, tuple[int, sqlite3.Row]] = {}
    for row in candidates:
        person_id = str(row["person_id"])
        if person_id in exclude_ids:
            continue
        distance = min(
            _edit_distance(row["compact"], variant, max_distance) for variant in compact_variants
        )
        if distance > max_distance:
            continue
        current = best_by_person.get(person_id)
        if current is None or distance < current[0]:
            best_by_person[person_id] = (distance, row)

    ranked = sorted(
        best_by_person.values(),
        key=lambda item: (item[0], -item[1]["degree"], -item[1]["weighted_degree"], item[1]["name"]),
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
    st = store()
    q = q.strip()

    # Numeric ID → exact match first
    if q.isdigit():
        rows = [
            (str(row["id"]), row["name"], row["name_cn"], row["name_tw"], row["degree"])
            for row in st.read(
                """
                SELECT g.id, p.name, p.name_cn, p.name_tw, g.degree
                FROM galaxy_node g JOIN person p ON p.id = g.id
                WHERE g.id = ?
                """,
                (int(q),),
            )
        ][:limit]
        remaining = limit - len(rows)
        if remaining > 0:
            rows.extend(_search_person_rows(st, q, remaining, exclude_id=int(q)))
    else:
        rows = _search_person_rows(st, q, limit)
        if len(rows) < limit:
            seen_ids = {row[0] for row in rows}
            rows.extend(_fuzzy_search_person_rows(st, q, limit - len(rows), exclude_ids=seen_ids))

    return row_dicts(rows, ["id", "name", "nameCn", "nameTw", "degree"])


# --- Frontend ---------------------------------------------------------------
# In production one container serves both: STAFF_GALAXY_STATIC points at the
# Vite build (frontend/dist). Registered last so every /api route wins.
_STATIC_DIR = os.environ.get("STAFF_GALAXY_STATIC")

if _STATIC_DIR:
    _static_root = Path(_STATIC_DIR).resolve()
    _index_html = _static_root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> Response:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (_static_root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(_static_root):
            # Vite fingerprints everything under assets/, so it never changes in place.
            immutable = path.startswith("assets/")
            return FileResponse(
                candidate,
                headers={
                    "Cache-Control": "public, max-age=31536000, immutable"
                    if immutable
                    else "public, max-age=3600"
                },
            )
        # History-API routes (/person/:id, /path, /compare) all boot the SPA.
        return FileResponse(_index_html, headers={"Cache-Control": "no-cache"})
