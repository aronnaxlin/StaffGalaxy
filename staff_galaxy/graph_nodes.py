from __future__ import annotations

import math
from dataclasses import dataclass

from neo4j import Driver

from .graph_db import read, write, write_batches


@dataclass(frozen=True)
class GraphNodeStats:
    node_count: int
    nodes_with_visible_edges: int
    max_visible_degree: int
    max_node_size: float
    role_layer: str
    layout_method: str


GOLDEN_ANGLE = 2.399963229728653


def build_graph_nodes(
    driver: Driver,
    *,
    min_role_weight: float = 12.0,
) -> GraphNodeStats:
    """Label galaxy members as :GalaxyNode and store degree, size, and a spiral seed position.

    Members are every person with at least one credit at role_weight >=
    min_role_weight. build_hierarchical_layout later overwrites x/y/community.
    """
    layout_method = "deterministic_spiral_v1"
    rows = read(
        driver,
        """
        MATCH (p:Person)
        WHERE EXISTS { (p)-[r:CREDITED]->() WHERE r.role_weight >= $min_role_weight }
        OPTIONAL MATCH (p)-[e:COLLAB]-()
        RETURN p.id AS person_id,
               count(e) AS visible_degree,
               coalesce(sum(e.collaboration_score), 0.0) AS visible_weighted_degree
        """,
        min_role_weight=min_role_weight,
    )
    rows.sort(key=lambda r: (-r["visible_weighted_degree"], -r["visible_degree"], r["person_id"]))

    role_layer = f"Weight >={min_role_weight}"
    total = len(rows)
    node_rows: list[dict[str, object]] = []
    for rn, row in enumerate(rows):
        radius = math.sqrt(rn / max(total - 1, 1)) * 1000.0
        angle = rn * GOLDEN_ANGLE
        weighted = float(row["visible_weighted_degree"])
        node_rows.append(
            {
                "person_id": row["person_id"],
                "x": math.cos(angle) * radius,
                "y": math.sin(angle) * radius,
                "visible_degree": int(row["visible_degree"]),
                "visible_weighted_degree": weighted,
                "node_size": 2.0 + min(10.0, math.log(1.0 + weighted) * 1.8),
                "role_layer": role_layer,
                "layout_method": layout_method,
            }
        )

    write(
        driver,
        """
        MATCH (p:GalaxyNode)
        REMOVE p:GalaxyNode, p.community_id, p.x, p.y, p.visible_degree,
               p.visible_weighted_degree, p.node_size, p.role_layer, p.layout_method
        """,
    )
    write_batches(
        driver,
        """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person_id})
        SET p:GalaxyNode,
            p.community_id = null,
            p.x = row.x,
            p.y = row.y,
            p.visible_degree = row.visible_degree,
            p.visible_weighted_degree = row.visible_weighted_degree,
            p.node_size = row.node_size,
            p.role_layer = row.role_layer,
            p.layout_method = row.layout_method
        """,
        node_rows,
    )

    return GraphNodeStats(
        node_count=total,
        nodes_with_visible_edges=sum(1 for row in node_rows if row["visible_degree"]),
        max_visible_degree=max((int(row["visible_degree"]) for row in node_rows), default=0),  # type: ignore[call-overload]
        max_node_size=max((float(row["node_size"]) for row in node_rows), default=0.0),  # type: ignore[arg-type]
        role_layer=role_layer,
        layout_method=layout_method,
    )
