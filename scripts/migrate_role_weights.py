"""One-shot migration: apply new role weights and rebuild edge/node tables."""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from staff_galaxy.database import connect_database, create_supporting_views, create_indexes
from staff_galaxy.roles import ROLE_DEFINITIONS
from staff_galaxy.search_index import build_person_search_terms
from staff_galaxy.visible_edges import build_person_collaboration_edges, build_visible_person_edges
from staff_galaxy.graph_nodes import build_graph_nodes


def migrate(db_path: Path) -> None:
    conn = connect_database(db_path)
    try:
        # 1. Update staff_positions
        print("Updating staff_positions...", flush=True)
        for pos_id, role_def in ROLE_DEFINITIONS.items():
            conn.execute(
                """
                UPDATE staff_positions
                SET normalized_role = ?, role_tier = ?, role_weight = ?
                WHERE position_id = ?
                """,
                [role_def.normalized_role, role_def.role_tier, role_def.role_weight, pos_id],
            )

        # 2. Update credits (denormalized role_weight / role_tier)
        print("Updating credits...", flush=True)
        conn.execute(
            """
            UPDATE credits c
            SET
              normalized_role = COALESCE(
                (SELECT sp.normalized_role FROM staff_positions sp WHERE sp.position_id = c.position_id),
                c.normalized_role
              ),
              role_tier = COALESCE(
                (SELECT sp.role_tier FROM staff_positions sp WHERE sp.position_id = c.position_id),
                c.role_tier
              ),
              role_weight = COALESCE(
                (SELECT sp.role_weight FROM staff_positions sp WHERE sp.position_id = c.position_id),
                c.role_weight
              )
            """
        )

        # 3. Rebuild complete edges, visible edges, and graph nodes
        print("Rebuilding person_collaboration_edges...", flush=True)
        collaboration_stats = build_person_collaboration_edges(conn)

        print("Rebuilding visible_person_edges...", flush=True)
        edge_stats = build_visible_person_edges(conn, min_role_weight=12.0, top_k=10)

        print("Rebuilding graph_nodes...", flush=True)
        node_stats = build_graph_nodes(conn, min_role_weight=12.0)

        print("Rebuilding person_search_terms...", flush=True)
        search_stats = build_person_search_terms(conn)

        create_supporting_views(conn)
        create_indexes(conn)

        print(
            f"Done. {collaboration_stats.edge_count:,} complete edges, "
            f"{edge_stats.edge_count:,} visible edges, {node_stats.node_count:,} nodes "
            f"(role_layer={node_stats.role_layer}), {search_stats.term_count:,} search terms.",
            flush=True,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    db = Path("data/processed/staff_galaxy.duckdb")
    if not db.exists():
        print(f"Database not found: {db}", file=sys.stderr)
        sys.exit(1)
    migrate(db)
