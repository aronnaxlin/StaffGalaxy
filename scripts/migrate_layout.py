"""Recompute graph node coordinates with the hierarchical Leiden layout.

Updates graph_nodes.community_id / x / y / layout_method in place — no
re-ingest required. Run after build_graph_nodes (or any role-weight change
that rebuilds visible_person_edges).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from staff_galaxy.database import connect_database
from staff_galaxy.layout import build_hierarchical_layout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/processed/staff_galaxy.duckdb"))
    parser.add_argument("--resolution", type=float, default=1.0, help="Leiden resolution parameter")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    conn = connect_database(args.db)
    try:
        stats = build_hierarchical_layout(conn, resolution=args.resolution, seed=args.seed)
    finally:
        conn.close()

    print(
        f"Layout {stats.layout_method}: {stats.node_count:,} nodes, {stats.edge_count:,} edges, "
        f"{stats.community_count:,} communities (largest {stats.largest_community_size:,}), "
        f"{stats.isolated_node_count:,} isolates on outer ring, "
        f"{stats.elapsed_seconds}s.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
