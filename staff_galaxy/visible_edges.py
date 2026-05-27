from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class VisibleEdgeStats:
    edge_count: int
    node_count: int
    shared_works_ge_2_edges: int
    top_k: int
    role_layer: str


def build_visible_person_edges(
    conn: duckdb.DuckDBPyConnection,
    *,
    role_tier: str = "A",
    top_k: int = 10,
) -> VisibleEdgeStats:
    conn.execute("DELETE FROM visible_person_edges")
    conn.execute("DROP TABLE IF EXISTS tier_visible_subject_people")
    conn.execute("DROP TABLE IF EXISTS tier_visible_candidate_edges")
    conn.execute("DROP TABLE IF EXISTS tier_visible_ranked_edges")

    conn.execute(
        """
        CREATE TEMP TABLE tier_visible_subject_people AS
        SELECT
          subject_id,
          person_id,
          MAX(role_weight) AS role_weight
        FROM credits
        WHERE role_tier = ?
        GROUP BY subject_id, person_id
        """,
        [role_tier],
    )

    conn.execute(
        """
        CREATE TEMP TABLE tier_visible_candidate_edges AS
        SELECT
          a.person_id AS source_person_id,
          b.person_id AS target_person_id,
          COUNT(*)::INTEGER AS shared_works_count,
          SUM(SQRT(a.role_weight * b.role_weight))::DOUBLE AS collaboration_score,
          MIN(s.year)::INTEGER AS first_year,
          MAX(s.year)::INTEGER AS last_year
        FROM tier_visible_subject_people a
        JOIN tier_visible_subject_people b
          ON a.subject_id = b.subject_id
         AND a.person_id < b.person_id
        JOIN subjects s ON s.id = a.subject_id
        GROUP BY a.person_id, b.person_id
        """
    )

    conn.execute(
        """
        CREATE TEMP TABLE tier_visible_ranked_edges AS
        WITH endpoint_ranks AS (
          SELECT
            source_person_id,
            target_person_id,
            ROW_NUMBER() OVER (
              PARTITION BY source_person_id
              ORDER BY collaboration_score DESC, shared_works_count DESC, target_person_id
            ) AS endpoint_rank
          FROM tier_visible_candidate_edges
          UNION ALL
          SELECT
            source_person_id,
            target_person_id,
            ROW_NUMBER() OVER (
              PARTITION BY target_person_id
              ORDER BY collaboration_score DESC, shared_works_count DESC, source_person_id
            ) AS endpoint_rank
          FROM tier_visible_candidate_edges
        )
        SELECT
          source_person_id,
          target_person_id,
          MIN(endpoint_rank)::INTEGER AS top_neighbor_rank
        FROM endpoint_ranks
        GROUP BY source_person_id, target_person_id
        """
    )

    conn.execute(
        """
        INSERT INTO visible_person_edges
        SELECT
          e.source_person_id,
          e.target_person_id,
          e.shared_works_count,
          e.collaboration_score,
          e.first_year,
          e.last_year,
          ? AS role_layer,
          r.top_neighbor_rank,
          CASE
            WHEN e.shared_works_count >= 2 AND r.top_neighbor_rank <= ?
              THEN 'shared_works_ge_2_and_top_k'
            WHEN e.shared_works_count >= 2
              THEN 'shared_works_ge_2'
            ELSE 'top_k'
          END AS selection_reason
        FROM tier_visible_candidate_edges e
        JOIN tier_visible_ranked_edges r
          ON r.source_person_id = e.source_person_id
         AND r.target_person_id = e.target_person_id
        WHERE e.shared_works_count >= 2 OR r.top_neighbor_rank <= ?
        """,
        [f"Tier {role_tier}", top_k, top_k],
    )

    edge_count = conn.execute("SELECT COUNT(*) FROM visible_person_edges").fetchone()[0]
    node_count = conn.execute(
        """
        SELECT COUNT(DISTINCT person_id)
        FROM (
          SELECT source_person_id AS person_id FROM visible_person_edges
          UNION ALL
          SELECT target_person_id AS person_id FROM visible_person_edges
        )
        """
    ).fetchone()[0]
    shared_works_ge_2_edges = conn.execute(
        "SELECT COUNT(*) FROM visible_person_edges WHERE shared_works_count >= 2"
    ).fetchone()[0]
    return VisibleEdgeStats(
        edge_count=int(edge_count),
        node_count=int(node_count),
        shared_works_ge_2_edges=int(shared_works_ge_2_edges),
        top_k=top_k,
        role_layer=f"Tier {role_tier}",
    )

