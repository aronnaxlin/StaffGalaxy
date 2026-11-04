"""Community labels for the galaxy view: who sits at the center of each circle.

Top level: the Leiden communities the layout already uses (the buffers'
community segment). The large ones are a thousand people or more, and the
clusters a viewer actually sees inside them are the sub-communities, so every
community of at least SPLIT_MIN_SIZE is split once more with Leiden on its own
backbone edges. Each labelled circle gets:

- people: the members with the highest in-circle weighted degree (sum of
  collaboration scores to other members). The score already carries role
  weights, and staying inside the circle keeps cross-circle brokers out.
- works: the anime with the most members in a main role (weight >= 12).
- x/y/radius: median position and the 75th-percentile distance from it, in
  Cosmos space, so the frontend can place a label and decide when it fits.

    .venv/bin/python -m staff_galaxy.communities [--store data/deploy/staff_galaxy.sqlite]

recomputes them into an existing store; `staff_galaxy.export` does the same
on every export.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import igraph as ig
import leidenalg
import numpy as np

from .graph_buffers import parse_segment_table
from .layout import NO_COMMUNITY
from .store import DEFAULT_STORE_PATH

TOP_MIN_SIZE = 20
SPLIT_MIN_SIZE = 150
SUB_MIN_SIZE = 12
PEOPLE_PER_LABEL = 3
WORKS_PER_LABEL = 2
MAIN_ROLE_WEIGHT = 12.0
SEED = 42


def _segment(payload: bytes, table: dict[str, tuple[int, int]], name: str, dtype: Any) -> np.ndarray:
    offset, count = table[name]
    return np.frombuffer(payload, dtype=dtype, count=count, offset=offset)


def _intra_strength(pairs: np.ndarray, weights: np.ndarray, group: np.ndarray, n: int) -> np.ndarray:
    inside = group[pairs[:, 0]] == group[pairs[:, 1]]
    strength = np.zeros(n)
    np.add.at(strength, pairs[inside, 0], weights[inside])
    np.add.at(strength, pairs[inside, 1], weights[inside])
    return strength


def build_community_labels(conn: sqlite3.Connection, payload: bytes, meta: dict[str, Any]) -> list[dict[str, Any]]:
    table = parse_segment_table(payload)
    community = _segment(payload, table, "community", np.uint16).astype(np.int64)
    positions = _segment(payload, table, "positions", np.float32).reshape(-1, 2).astype(np.float64)
    pairs = _segment(payload, table, "edgePairs", np.uint32).reshape(-1, 2).astype(np.int64)
    weights = _segment(payload, table, "edgeWeights", np.float32).astype(np.float64)
    person_ids = np.array([int(node["id"]) for node in meta["nodes"]], dtype=np.int64)
    n = len(person_ids)

    # Sub-community per node, -1 where the community is not split.
    sub = np.full(n, -1, dtype=np.int64)
    same = community[pairs[:, 0]] == community[pairs[:, 1]]
    sizes = Counter(int(c) for c in community if c != NO_COMMUNITY)
    for c, size in sizes.items():
        if size < SPLIT_MIN_SIZE:
            continue
        members = np.flatnonzero(community == c)
        local = np.full(n, -1, dtype=np.int64)
        local[members] = np.arange(len(members))
        edges = same & (community[pairs[:, 0]] == c)
        graph = ig.Graph(n=len(members), edges=local[pairs[edges]].tolist())
        partition = leidenalg.find_partition(
            graph,
            leidenalg.RBConfigurationVertexPartition,
            weights=weights[edges].tolist(),
            seed=SEED,
            n_iterations=-1,
        )
        sub[members] = partition.membership

    top_strength = _intra_strength(pairs, weights, community, n)
    # Unique key per (community, sub-community) so one pass covers both levels.
    sub_key = np.where(sub >= 0, community * 100_000 + sub, -1 - np.arange(n))
    sub_strength = _intra_strength(pairs, weights, sub_key, n)

    index_of = {int(pid): i for i, pid in enumerate(person_ids)}
    works_by_node: dict[int, list[int]] = defaultdict(list)
    for person_id, anime_id in conn.execute(
        "SELECT DISTINCT person_id, anime_id FROM credit WHERE role_weight >= ? AND NOT nsfw",
        (MAIN_ROLE_WEIGHT,),
    ):
        i = index_of.get(person_id)
        if i is not None:
            works_by_node[i].append(anime_id)
    anime = {
        row[0]: row[1:]
        for row in conn.execute("SELECT id, name, name_cn, year FROM anime WHERE NOT nsfw")
    }

    def describe(level: int, key: str, parent: int, members: np.ndarray, strength: np.ndarray) -> dict[str, Any]:
        center = np.median(positions[members], axis=0)
        radius = float(np.percentile(np.linalg.norm(positions[members] - center, axis=1), 75))
        top = members[np.lexsort((person_ids[members], -strength[members]))[:PEOPLE_PER_LABEL]]
        work_counts: Counter[int] = Counter()
        for i in members:
            work_counts.update(works_by_node.get(int(i), ()))
        top_works = sorted(work_counts.items(), key=lambda item: (-item[1], item[0]))[:WORKS_PER_LABEL]
        member_years = [
            anime[a][2] for i in members for a in works_by_node.get(int(i), ()) if anime.get(a) and anime[a][2]
        ]
        return {
            "level": level,
            "id": key,
            "parent": parent,
            "size": len(members),
            "x": round(float(center[0]), 1),
            "y": round(float(center[1]), 1),
            "radius": round(radius, 1),
            "people": [str(int(person_ids[i])) for i in top],
            "works": [
                {"subjectId": str(a), "subjectName": anime[a][0], "subjectNameCn": anime[a][1]}
                for a, _ in top_works
                if a in anime
            ],
            "year": int(np.median(member_years)) if member_years else None,
        }

    labels: list[dict[str, Any]] = []
    for c, size in sorted(sizes.items(), key=lambda item: (-item[1], item[0])):
        if size < TOP_MIN_SIZE:
            continue
        members = np.flatnonzero(community == c)
        labels.append(describe(0, str(c), c, members, top_strength))
        if size < SPLIT_MIN_SIZE:
            continue
        sub_sizes = Counter(int(s) for s in sub[members])
        for s, sub_size in sorted(sub_sizes.items(), key=lambda item: (-item[1], item[0])):
            if sub_size >= SUB_MIN_SIZE:
                labels.append(describe(1, f"{c}.{s}", c, members[sub[members] == s], sub_strength))
    return labels


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute galaxy community labels inside a deploy store.")
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE_PATH)
    args = parser.parse_args()

    conn = sqlite3.connect(args.store)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta WHERE key IN ('graph_buffers', 'graph_meta')"))
        labels = build_community_labels(conn, meta["graph_buffers"], json.loads(meta["graph_meta"]))
        conn.execute(
            "INSERT OR REPLACE INTO meta VALUES ('community_labels', ?)",
            (json.dumps(labels, ensure_ascii=False).encode(),),
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Wrote {sum(l['level'] == 0 for l in labels)} communities and "
          f"{sum(l['level'] == 1 for l in labels)} sub-communities to {args.store}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
