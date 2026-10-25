"""Binary graph transport for the galaxy view (edge-rendering plan Phase 2).

Single-request segmented buffer replacing the per-level JSON endpoints:

    [header: magic + version + nodeCount + edgeCount + segment table]
    [positions  : Float32  nodeCount×2 ]  pre-normalized to Cosmos space
    [sizes      : Float32  nodeCount   ]
    [colors     : Uint8    nodeCount×4 ]  RGBA base color (community hue is client-side)
    [community  : Uint16   nodeCount   ]  Leiden community id, 0xFFFF = isolate
    [edgePairs  : Uint32   edgeCount×2 ]  node indices (meta JSON maps index → person id)
    [edgeWeights: Float32  edgeCount   ]  collaboration_score
    [edgeShared : Uint16   edgeCount   ]  shared_works_count (edge LOD prefix sort key)

Node order: visible_weighted_degree DESC — the same prefix order the frontend
uses for default labels. Edge order: shared_works_count DESC,
collaboration_score DESC — any zoom budget is a zero-copy prefix slice.

Node names/degrees live in the JSON meta endpoint (anvaka labels.json
equivalent), decoupled from geometry.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Any

import numpy as np
from neo4j import Driver

from .graph_db import read, read_one
from .layout import NO_COMMUNITY
from .search_index import extract_person_name_cn, extract_person_name_tw

MAGIC = b"SGX1"
# Version 2: every segment offset is aligned up to 4 bytes so the frontend can
# construct typed-array views directly (Float32Array/Uint32Array throw on
# misaligned byteOffset). Version 1 packed segments back-to-back.
VERSION = 2

SEGMENT_NAMES = (
    "positions",
    "sizes",
    "colors",
    "community",
    "edgePairs",
    "edgeWeights",
    "edgeShared",
)
SEGMENT_COUNT = len(SEGMENT_NAMES)
HEADER_SIZE = 4 + 4 + 4 + 4 + SEGMENT_COUNT * 8

# Must match the frontend Cosmos space (CosmosGalaxyView COSMOS_SPACE_SIZE /
# COSMOS_LAYOUT_SIZE) — positions are normalized here so the frontend uploads
# them verbatim.
COSMOS_SPACE_SIZE = 8192.0
COSMOS_LAYOUT_SIZE = 4300.0

# Keep Float32 headroom: raw x/y are rounded to 4 decimals on GalaxyNode, and
# the normalization below stays well inside Float32 precision at this scale.
UINT32_MAX = 0xFFFF_FFFF


@dataclass(frozen=True)
class GraphBuffers:
    payload: bytes
    meta: dict[str, Any]
    node_count: int
    edge_count: int
    layout_method: str
    cache_token: str


def _node_base_color(degree: int) -> tuple[int, int, int, int]:
    """Server-side port of the frontend graphBuilder gray ramp (0-255 RGBA)."""
    t = min(1.0, math.log10(1 + max(degree, 0)) / 3.5)
    v = round(195 + t * 60)
    return (v, v, v, 255)


def build_graph_buffers(driver: Driver) -> GraphBuffers:
    node_rows = [
        (
            row["person_id"],
            row["name"],
            row["infobox"],
            row["x"],
            row["y"],
            row["visible_degree"],
            row["visible_weighted_degree"],
            row["node_size"],
            row["community_id"],
            row["layout_method"],
        )
        for row in read(
            driver,
            """
            MATCH (p:GalaxyNode)
            RETURN p.id AS person_id, p.name AS name, p.infobox AS infobox,
                   p.x AS x, p.y AS y,
                   p.visible_degree AS visible_degree,
                   p.visible_weighted_degree AS visible_weighted_degree,
                   p.node_size AS node_size,
                   p.community_id AS community_id,
                   p.layout_method AS layout_method
            ORDER BY visible_weighted_degree DESC, visible_degree DESC, person_id
            """,
        )
    ]
    # Columnar fetch: four lists in one record decode far faster than 500K+
    # records, and numpy sorts faster than the server's ORDER BY.
    edge_columns = read_one(
        driver,
        """
        MATCH (s:GalaxyNode)-[e:COLLAB]->(t:GalaxyNode)
        RETURN collect(s.id) AS sources, collect(t.id) AS targets,
               collect(e.shared_works_count) AS shared, collect(e.collaboration_score) AS scores
        """,
    ) or {"sources": [], "targets": [], "shared": [], "scores": []}
    edge_sources = np.asarray(edge_columns["sources"], dtype=np.int64)
    edge_targets = np.asarray(edge_columns["targets"], dtype=np.int64)
    edge_shared_raw = np.asarray(edge_columns["shared"], dtype=np.int64)
    edge_scores = np.asarray(edge_columns["scores"], dtype=np.float64)
    # shared_works_count DESC, collaboration_score DESC, source, target
    order = np.lexsort((edge_targets, edge_sources, -edge_scores, -edge_shared_raw))

    node_count = len(node_rows)
    edge_count = len(order)
    if node_count > UINT32_MAX or edge_count > UINT32_MAX:
        raise ValueError("graph too large for u32 buffer indices")

    person_ids = np.fromiter((int(r[0]) for r in node_rows), dtype=np.int64, count=node_count)

    # --- positions, normalized to Cosmos space (span 4300 centered in 8192) --
    xs = np.fromiter((float(r[3]) for r in node_rows), dtype=np.float64, count=node_count)
    ys = np.fromiter((float(r[4]) for r in node_rows), dtype=np.float64, count=node_count)
    span = max(float(xs.max() - xs.min()), float(ys.max() - ys.min()), 1.0)
    center_x = (float(xs.max()) + float(xs.min())) / 2
    center_y = (float(ys.max()) + float(ys.min())) / 2
    positions = np.empty(node_count * 2, dtype=np.float32)
    positions[0::2] = COSMOS_SPACE_SIZE / 2 + (xs - center_x) / span * COSMOS_LAYOUT_SIZE
    positions[1::2] = COSMOS_SPACE_SIZE / 2 + (ys - center_y) / span * COSMOS_LAYOUT_SIZE

    # Global-view point size, matching the previous client-side mapping.
    sizes = np.fromiter(
        (max(1.8, float(r[7] or 0.0) * 0.55) for r in node_rows),
        dtype=np.float32,
        count=node_count,
    )

    colors = np.empty(node_count * 4, dtype=np.uint8)
    for i, row in enumerate(node_rows):
        r, g, b, a = _node_base_color(int(row[5] or 0))
        colors[i * 4 : i * 4 + 4] = (r, g, b, a)

    community = np.fromiter(
        (int(r[8]) if r[8] is not None else NO_COMMUNITY for r in node_rows),
        dtype=np.uint16,
        count=node_count,
    )

    # Map person ids to node indices (node order is weighted-degree DESC).
    id_order = np.argsort(person_ids, kind="stable")
    sorted_ids = person_ids[id_order]
    edge_pairs = np.empty(edge_count * 2, dtype=np.uint32)
    edge_pairs[0::2] = id_order[np.searchsorted(sorted_ids, edge_sources[order])]
    edge_pairs[1::2] = id_order[np.searchsorted(sorted_ids, edge_targets[order])]
    edge_weights = edge_scores[order].astype(np.float32)
    edge_shared = np.minimum(edge_shared_raw[order], 0xFFFF).astype(np.uint16)

    segments: list[tuple[str, np.ndarray]] = [
        ("positions", positions),
        ("sizes", sizes),
        ("colors", colors),
        ("community", community),
        ("edgePairs", edge_pairs),
        ("edgeWeights", edge_weights),
        ("edgeShared", edge_shared),
    ]

    header_parts = [struct.pack("<4sIII", MAGIC, VERSION, node_count, edge_count)]
    body_parts: list[bytes] = []
    offset = HEADER_SIZE
    for name, array in segments:
        aligned = (offset + 3) & ~3
        header_parts.append(struct.pack("<II", aligned, array.size))
        body_parts.append(b"\x00" * (aligned - offset))
        body_parts.append(array.tobytes())
        offset = aligned + array.nbytes
    payload = b"".join(header_parts) + b"".join(body_parts)

    layout_methods = {str(r[9]) for r in node_rows}
    layout_method = layout_methods.pop() if len(layout_methods) == 1 else "mixed"

    meta = {
        "nodeCount": node_count,
        "edgeCount": edge_count,
        "layoutMethod": layout_method,
        "nodes": [
            {
                "id": str(int(row[0])),
                "name": row[1],
                "nameCn": extract_person_name_cn(row[2] or ""),
                "nameTw": extract_person_name_tw(row[2] or ""),
                "degree": int(row[5] or 0),
                "weightedDegree": float(row[6] or 0.0),
            }
            for row in node_rows
        ],
    }

    return GraphBuffers(
        payload=payload,
        meta=meta,
        node_count=node_count,
        edge_count=edge_count,
        layout_method=layout_method,
        cache_token="",
    )


def parse_segment_table(payload: bytes) -> dict[str, tuple[int, int]]:
    """(offset, elementCount) per segment — used by tests and the frontend mirror."""
    if payload[:4] != MAGIC:
        raise ValueError("bad magic")
    _, node_count, edge_count = struct.unpack_from("<III", payload, 4)
    _ = node_count, edge_count
    table: dict[str, tuple[int, int]] = {}
    for i, name in enumerate(SEGMENT_NAMES):
        offset, count = struct.unpack_from("<II", payload, 16 + i * 8)
        table[name] = (offset, count)
    return table
