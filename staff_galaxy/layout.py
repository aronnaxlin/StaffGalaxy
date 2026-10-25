"""Hierarchical Leiden + force-directed layout for the visible galaxy graph.

Replaces the deterministic spiral (`deterministic_spiral_v1`) with the
two-level recipe validated by map-of-github (see
docs/staff-galaxy/edge-rendering-performance-plan.md §4.4 / Phase 3):

1. Leiden community detection on the visible staff-collaboration graph
   (edges weighted by collaboration_score).
2. Inter-cluster layout: every community collapses to a super-node
   (super-edge weight = sum of cross-community collaboration_score) and a
   Fruchterman-Reingold pass yields cluster centroids.
3. Intra-cluster layout: each community is laid out on its own
   (Fruchterman-Reingold for small communities, DrL for large ones), then
   scaled to a radius proportional to sqrt(size) and translated onto its
   centroid.

Nodes with no visible edges (isolates) are excluded from community
detection output (community_id = NULL) and placed on an outer ring so the
connected core stays readable.

Writes back GalaxyNode.community_id / x / y / layout_method.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import igraph as ig
import leidenalg
import numpy as np
from neo4j import Driver

from .graph_db import read, write_batches

LAYOUT_METHOD = "hier_leiden_fr_v1"

# Communities larger than this use DrL (near-linear) instead of Fruchterman-
# Reingold (O(n^2) per iteration) — a 5K-node community at 500 FR iterations
# would be minutes; DrL does it in seconds.
FR_NODE_LIMIT = 1_500

# Buffers carry community ids in a Uint16 segment; isolates use this sentinel.
NO_COMMUNITY = 0xFFFF


@dataclass(frozen=True)
class LayoutStats:
    node_count: int
    edge_count: int
    community_count: int
    largest_community_size: int
    isolated_node_count: int
    layout_method: str
    elapsed_seconds: float


def _layout_cluster(graph: ig.Graph) -> np.ndarray:
    """2-D coordinates for one community subgraph, centered on the origin."""
    n = graph.vcount()
    if n == 1:
        return np.zeros((1, 2))
    if n <= 4:
        angles = np.arange(n) * (2.0 * math.pi / n)
        return np.column_stack([np.cos(angles), np.sin(angles)])

    weights = graph.es["weight"] if "weight" in graph.es.attributes() else None
    if n > FR_NODE_LIMIT:
        layout = graph.layout_drl(weights=weights)
    else:
        # Deterministic spiral seed reduces variance between rebuilds.
        idx = np.arange(n)
        seed = np.column_stack(
            [
                np.sqrt(idx / max(n - 1, 1)) * np.cos(idx * 2.399963229728653),
                np.sqrt(idx / max(n - 1, 1)) * np.sin(idx * 2.399963229728653),
            ]
        )
        layout = graph.layout_fruchterman_reingold(weights=weights, niter=500, seed=seed.tolist())
    return np.asarray(layout.coords, dtype=float)


def _fit_to_radius(coords: np.ndarray, radius: float) -> np.ndarray:
    """Center coords on the origin and scale so the farthest point is at radius."""
    coords = coords - coords.mean(axis=0)
    max_dist = float(np.hypot(coords[:, 0], coords[:, 1]).max())
    if max_dist > 0:
        coords = coords * (radius / max_dist)
    return coords


def _pack_communities(
    coords: np.ndarray,
    radii: np.ndarray,
    sizes: np.ndarray,
    *,
    padding: float = 1.12,
    iterations: int = 400,
    tol: float = 0.01,
) -> np.ndarray:
    """Push community centroids apart until circles of the given radii no longer
    overlap (d3-forceCollide-style relaxation). Weighted FR alone leaves the
    giant hub communities nearly coincident — without this pass the galaxy
    renders as one bright blob."""
    coords = coords.copy().astype(float)
    n = len(coords)
    if n <= 1:
        return coords
    sizes = sizes.astype(float)
    for _ in range(iterations):
        max_move = 0.0
        for i in range(n):
            delta = coords[i] - coords
            dist = np.hypot(delta[:, 0], delta[:, 1])
            overlap = (radii[i] + radii) * padding - dist
            overlap[i] = 0.0
            hits = np.flatnonzero(overlap > 0)
            for j in hits:
                if dist[j] < 1e-6:
                    angle = (i * 2.399963229728653 + j) % (2.0 * math.pi)
                    direction = np.array([math.cos(angle), math.sin(angle)])
                else:
                    direction = delta[j] / dist[j]
                # Heavier community moves less, and only half the overlap is
                # resolved per visit (the other half when j gets its turn).
                share = sizes[j] / (sizes[i] + sizes[j])
                move = direction * (overlap[j] * share * 0.5)
                coords[i] += move
                max_move = max(max_move, float(np.hypot(move[0], move[1])))
        if max_move < tol:
            break
    return coords


def build_hierarchical_layout(
    driver: Driver,
    *,
    resolution: float = 1.0,
    seed: int = 42,
    node_spacing: float = 1.0,
) -> LayoutStats:
    started = time.perf_counter()

    node_rows = read(driver, "MATCH (p:GalaxyNode) RETURN p.id AS person_id ORDER BY person_id")
    edge_rows = read(
        driver,
        """
        MATCH (s:GalaxyNode)-[e:COLLAB]->(t:GalaxyNode)
        RETURN s.id AS source, t.id AS target, e.collaboration_score AS score
        """,
    )

    person_ids = [int(row["person_id"]) for row in node_rows]
    index_of = {person_id: i for i, person_id in enumerate(person_ids)}
    n = len(person_ids)

    edges: list[tuple[int, int]] = []
    weights: list[float] = []
    degree = np.zeros(n, dtype=np.int64)
    for row in edge_rows:
        score = row["score"]
        s = index_of.get(int(row["source"]))
        t = index_of.get(int(row["target"]))
        if s is None or t is None:
            continue
        edges.append((s, t))
        w = float(score) if score and score > 0 else 0.1
        weights.append(w)
        degree[s] += 1
        degree[t] += 1

    graph = ig.Graph(n=n, edges=edges, directed=False)
    graph.es["weight"] = weights
    graph.simplify(multiple=True, loops=False, combine_edges="sum")
    weights = list(graph.es["weight"])

    # --- Level 0: Leiden communities -------------------------------------
    partition = leidenalg.find_partition(
        graph,
        leidenalg.RBConfigurationVertexPartition,
        weights=weights,
        resolution_parameter=resolution,
        seed=seed,
        n_iterations=-1,
    )
    raw_membership = np.asarray(partition.membership, dtype=np.int64)

    # Remap community ids deterministically: 0 = largest community.
    raw_sizes = np.bincount(raw_membership)
    order = np.argsort(-raw_sizes, kind="stable")
    remap = np.empty(len(order), dtype=np.int64)
    remap[order] = np.arange(len(order))
    membership = remap[raw_membership]
    community_sizes = np.bincount(membership)
    community_count = len(community_sizes)

    # Leiden gives every isolate its own singleton community; exclude those
    # from the inter-cluster layout entirely (they go on the outer ring).
    isolate_community = np.array(
        [community_sizes[c] == 1 and degree[int(np.flatnonzero(membership == c)[0])] == 0
         for c in range(community_count)],
        dtype=bool,
    )
    connected_ids = np.flatnonzero(~isolate_community)
    connected_index = {int(c): i for i, c in enumerate(connected_ids)}
    connected_count = len(connected_ids)

    # --- Level 1: inter-cluster layout ------------------------------------
    # Super-graph: one vertex per connected community; super-edge weight = sum
    # of cross-community collaboration scores.
    edge_sources = np.asarray([e.source for e in graph.es], dtype=np.int64)
    edge_targets = np.asarray([e.target for e in graph.es], dtype=np.int64)
    edge_weights = np.asarray(weights, dtype=float)
    comm_of_source = membership[edge_sources]
    comm_of_target = membership[edge_targets]
    cross = comm_of_source != comm_of_target

    super_pairs: dict[tuple[int, int], float] = {}
    for a, b, w in zip(comm_of_source[cross], comm_of_target[cross], edge_weights[cross]):
        ia, ib = connected_index.get(int(a)), connected_index.get(int(b))
        if ia is None or ib is None:
            continue
        key = (ia, ib) if ia < ib else (ib, ia)
        super_pairs[key] = super_pairs.get(key, 0.0) + float(w)

    centroids = np.zeros((community_count, 2))
    if connected_count > 0:
        super_graph = ig.Graph(n=connected_count, edges=list(super_pairs), directed=False)
        super_graph.es["weight"] = list(super_pairs.values())
        super_coords = _layout_cluster(super_graph) if connected_count > 1 else np.zeros((1, 2))

        connected_sizes = community_sizes[connected_ids]
        radii = node_spacing * np.sqrt(community_sizes.astype(float))
        connected_radii = radii[connected_ids]
        if connected_count > 1:
            # Pre-scale FR output near the *packed* extent (enclosing circle of
            # all community circles with slack), then circle-pack so centroid
            # distances respect r_i + r_j. Two failure modes bracket this:
            # FR raw leaves giant hubs nearly coincident (bright blob), while
            # pre-scaling to sum(radii) spreads small communities so far the
            # core shrinks to a dot — the packed-circle estimate lands between.
            packed_radius = float(np.sqrt((connected_radii**2).sum()))
            target_span = packed_radius * 2.0 * 2.2
            span = float(np.ptp(super_coords, axis=0).max())
            if span > 0:
                super_coords = super_coords * (target_span / span)
            super_coords = _pack_communities(super_coords, connected_radii, connected_sizes)
        for local_index, community_id in enumerate(connected_ids):
            centroids[community_id] = super_coords[local_index]
    radii = node_spacing * np.sqrt(community_sizes.astype(float))

    # --- Level 2: intra-cluster layout ------------------------------------
    positions = np.zeros((n, 2))
    for community_id in range(community_count):
        members = np.flatnonzero(membership == community_id)
        if isolate_community[community_id]:
            continue  # placed on the outer ring below
        centroid = centroids[community_id]
        if len(members) == 1:
            positions[members[0]] = centroid
            continue
        subgraph = graph.subgraph(members.tolist())
        local = _layout_cluster(subgraph)
        local = _fit_to_radius(local, float(radii[community_id]))
        positions[members] = local + centroid

    # Isolates (no visible edges) get no community and sit on an outer ring.
    isolated = np.flatnonzero(degree == 0)
    if len(isolated):
        ring_radius = float(np.hypot(positions[:, 0], positions[:, 1]).max() or 1.0) * 1.08
        ring_radius += node_spacing * 4
        angles = np.arange(len(isolated)) * (2.0 * math.pi / len(isolated))
        positions[isolated, 0] = np.cos(angles) * ring_radius
        positions[isolated, 1] = np.sin(angles) * ring_radius

    # --- Write back --------------------------------------------------------
    community_col: list[int | None] = []
    for i in range(n):
        community_col.append(None if degree[i] == 0 else int(membership[i]))

    write_batches(
        driver,
        """
        UNWIND $rows AS row
        MATCH (p:GalaxyNode {id: row.person_id})
        SET p.community_id = row.community_id,
            p.x = row.x,
            p.y = row.y,
            p.layout_method = row.layout_method
        """,
        (
            {
                "person_id": person_ids[i],
                "community_id": community_col[i],
                "x": round(float(positions[i, 0]), 4),
                "y": round(float(positions[i, 1]), 4),
                "layout_method": LAYOUT_METHOD,
            }
            for i in range(n)
        ),
    )

    return LayoutStats(
        node_count=n,
        edge_count=graph.ecount(),
        community_count=community_count,
        largest_community_size=int(community_sizes.max()) if community_count else 0,
        isolated_node_count=len(isolated),
        layout_method=LAYOUT_METHOD,
        elapsed_seconds=round(time.perf_counter() - started, 2),
    )
