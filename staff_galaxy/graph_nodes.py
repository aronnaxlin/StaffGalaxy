from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class GraphNodeStats:
    node_count: int
    nodes_with_visible_edges: int
    max_visible_degree: int
    max_node_size: float
    role_layer: str
    layout_method: str


def build_graph_nodes(
    conn: duckdb.DuckDBPyConnection,
    *,
    min_role_weight: float = 12.0,
) -> GraphNodeStats:
    layout_method = "deterministic_spiral_v1"
    conn.execute("DELETE FROM graph_nodes")
    conn.execute("DROP TABLE IF EXISTS graph_node_metrics")

    conn.execute(
        """
        CREATE TEMP TABLE graph_node_metrics AS
        WITH tier_people AS (
          SELECT DISTINCT person_id
          FROM credits
          WHERE role_weight >= ?
        ),
        edge_degrees AS (
          SELECT
            person_id,
            COUNT(*)::INTEGER AS visible_degree,
            SUM(collaboration_score)::DOUBLE AS visible_weighted_degree
          FROM (
            SELECT source_person_id AS person_id, collaboration_score
            FROM visible_person_edges
            UNION ALL
            SELECT target_person_id AS person_id, collaboration_score
            FROM visible_person_edges
          )
          GROUP BY person_id
        )
        SELECT
          tp.person_id,
          COALESCE(ed.visible_degree, 0)::INTEGER AS visible_degree,
          COALESCE(ed.visible_weighted_degree, 0.0)::DOUBLE AS visible_weighted_degree
        FROM tier_people tp
        LEFT JOIN edge_degrees ed ON ed.person_id = tp.person_id
        """,
        [min_role_weight],
    )

    role_layer = f"Weight >={min_role_weight}"
    conn.execute(
        """
        INSERT INTO graph_nodes
        WITH ranked AS (
          SELECT
            person_id,
            visible_degree,
            visible_weighted_degree,
            ROW_NUMBER() OVER (
              ORDER BY visible_weighted_degree DESC, visible_degree DESC, person_id
            ) AS rn,
            COUNT(*) OVER () AS total_count
          FROM graph_node_metrics
        ),
        positioned AS (
          SELECT
            person_id,
            visible_degree,
            visible_weighted_degree,
            SQRT((rn - 1)::DOUBLE / GREATEST(total_count - 1, 1)) * 1000.0 AS radius,
            (rn - 1) * 2.399963229728653 AS angle
          FROM ranked
        )
        SELECT
          person_id,
          NULL::INTEGER AS community_id,
          COS(angle) * radius AS x,
          SIN(angle) * radius AS y,
          visible_degree,
          visible_weighted_degree,
          (2.0 + LEAST(10.0, LN(1.0 + visible_weighted_degree) * 1.8))::DOUBLE
            AS node_size,
          ? AS role_layer,
          ? AS layout_method
        FROM positioned
        """,
        [role_layer, layout_method],
    )

    row = conn.execute(
        """
        SELECT
          COUNT(*) AS node_count,
          COUNT(*) FILTER (WHERE visible_degree > 0) AS nodes_with_visible_edges,
          MAX(visible_degree) AS max_visible_degree,
          MAX(node_size) AS max_node_size
        FROM graph_nodes
        """
    ).fetchone()
    return GraphNodeStats(
        node_count=int(row[0]),
        nodes_with_visible_edges=int(row[1]),
        max_visible_degree=int(row[2] or 0),
        max_node_size=float(row[3] or 0.0),
        role_layer=role_layer,
        layout_method=layout_method,
    )
