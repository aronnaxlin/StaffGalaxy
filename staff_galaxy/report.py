from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import duckdb

from .graph_audit import LayerAudit
from .ingest import IngestStats


def write_audit_report(
    path: Path,
    conn: duckdb.DuckDBPyConnection,
    archive_name: str,
    archive_created_at: str,
    archive_size_bytes: int,
    ingest_stats: IngestStats,
    layer_audits: Sequence[LayerAudit],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.extend(
        [
            "# Staff Galaxy Data Audit",
            "",
            "## Snapshot",
            "",
            f"- Archive zip: `{archive_name}`",
            f"- Created at: `{archive_created_at or 'unknown'}`",
            f"- Zip size: `{archive_size_bytes:,}` bytes",
            "",
            "## Base Counts",
            "",
            "| Metric | Count |",
            "| --- | ---: |",
            f"| Anime subjects, `subject.type = 2` | {ingest_stats.anime_subject_count:,} |",
            f"| Real individual persons, `person.type = 1` | {ingest_stats.real_person_count:,} |",
            f"| Total subject-person rows | {ingest_stats.subject_person_rows_total:,} |",
            f"| Anime credits involving real individual people | {ingest_stats.anime_real_person_credits:,} |",
            f"| Real people with anime credits | {ingest_stats.real_people_with_anime_credits:,} |",
            f"| Anime subjects with real person credits | {ingest_stats.anime_subjects_with_real_person_credits:,} |",
            f"| Anime cast rows involving real individual people | {_single_int(conn, 'SELECT COUNT(*) FROM person_characters'):,} |",
            "",
            "### Subject Counts By Type",
            "",
        ]
    )
    lines.extend(_counter_table(ingest_stats.subject_count_by_type, "Type"))
    lines.extend(["", "### Person Counts By Type", ""])
    lines.extend(_counter_table(ingest_stats.person_count_by_type, "Type"))

    lines.extend(["", "## Top Raw Position IDs", ""])
    lines.extend(_query_table(
        conn,
        """
        SELECT position_id, position_cn, position_en, COUNT(*) AS credit_count
        FROM credits
        GROUP BY position_id, position_cn, position_en
        ORDER BY credit_count DESC, position_id
        LIMIT 40
        """,
        ("Position ID", "CN", "EN", "Credits"),
    ))

    lines.extend(["", "## Top Cast People By Anime Character Links", ""])
    lines.extend(_query_table(
        conn,
        """
        SELECT person_name, COUNT(*) AS cast_rows
        FROM cast_details
        GROUP BY person_name
        ORDER BY cast_rows DESC, person_name
        LIMIT 20
        """,
        ("Person", "Cast Rows"),
    ))

    lines.extend(["", "## Normalized Role Counts", ""])
    lines.extend(_query_table(
        conn,
        """
        SELECT normalized_role, role_tier, COUNT(*) AS credit_count
        FROM credits
        WHERE normalized_role IS NOT NULL
        GROUP BY normalized_role, role_tier
        ORDER BY credit_count DESC, normalized_role
        """,
        ("Role", "Tier", "Credits"),
    ))

    unmapped = conn.execute(
        "SELECT COUNT(*) FROM credits WHERE normalized_role IS NULL"
    ).fetchone()[0]
    tier_d = conn.execute(
        "SELECT COUNT(*) FROM credits WHERE role_tier = 'D'"
    ).fetchone()[0]
    lines.extend(
        [
            "",
            f"Unmapped anime-person credits: `{unmapped:,}`.",
            f"Tier D load-more anime-person credits: `{tier_d:,}`.",
            "",
            "### Top Tier D Positions",
            "",
        ]
    )
    lines.extend(_query_table(
        conn,
        """
        SELECT position_id, position_cn, position_en, COUNT(*) AS credit_count
        FROM credits
        WHERE role_tier = 'D'
        GROUP BY position_id, position_cn, position_en
        ORDER BY credit_count DESC, position_id
        LIMIT 30
        """,
        ("Position ID", "CN", "EN", "Credits"),
    ))

    lines.extend(["", "## Candidate Graph Scale", ""])
    for audit in layer_audits:
        lines.extend(_layer_section(audit))

    visible_summary = conn.execute(
        """
        SELECT
          COUNT(*) AS edge_count,
          COUNT(DISTINCT source_person_id) AS source_count,
          COUNT(DISTINCT target_person_id) AS target_count,
          COUNT(*) FILTER (WHERE shared_works_count >= 2) AS shared_ge_2,
          COUNT(*) FILTER (WHERE selection_reason = 'top_k') AS top_k_only
        FROM visible_person_edges
        """
    ).fetchone()
    visible_nodes = conn.execute(
        """
        SELECT COUNT(DISTINCT person_id)
        FROM (
          SELECT source_person_id AS person_id FROM visible_person_edges
          UNION ALL
          SELECT target_person_id AS person_id FROM visible_person_edges
        )
        """
    ).fetchone()[0]
    lines.extend(
        [
            "",
            "## Built Visible Backbone",
            "",
            "The database currently builds the MVP global graph backbone from Tier A with this rule:",
            "",
            "```text",
            "sharedWorksCount >= 2 OR top 10 strongest neighbors per endpoint",
            "```",
            "",
            "| Metric | Count |",
            "| --- | ---: |",
            f"| Visible nodes | {visible_nodes:,} |",
            f"| Visible edges | {visible_summary[0]:,} |",
            f"| Edges with `sharedWorksCount >= 2` | {visible_summary[3]:,} |",
            f"| Top-10-only edges | {visible_summary[4]:,} |",
            "",
        ]
    )
    graph_node_summary = conn.execute(
        """
        SELECT
          COUNT(*) AS node_count,
          COUNT(*) FILTER (WHERE visible_degree > 0) AS nodes_with_edges,
          MAX(visible_degree) AS max_degree,
          ROUND(MAX(node_size), 2) AS max_size,
          MIN(layout_method) AS layout_method
        FROM graph_nodes
        """
    ).fetchone()
    lines.extend(
        [
            "## Built Graph Nodes",
            "",
            "The database also materializes Tier A graph nodes. Coordinates currently use a deterministic spiral placeholder so exports are stable before the later ForceAtlas2 layout phase.",
            "",
            "| Metric | Count |",
            "| --- | ---: |",
            f"| Graph nodes | {graph_node_summary[0]:,} |",
            f"| Nodes with visible edges | {graph_node_summary[1]:,} |",
            f"| Max visible degree | {graph_node_summary[2]:,} |",
            f"| Max node size | {graph_node_summary[3]} |",
            f"| Layout method | `{graph_node_summary[4]}` |",
            "",
        ]
    )

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Use Tier A for the first global backbone graph.",
            "",
            "Tier A is the best first default because it preserves the main creator network while keeping graph density manageable. "
            "Tier A+B is valuable for local expansion and person detail, but is too dense for the initial global view. "
            "Tier C should remain in normal person detail. Tier D should stay behind load-more/full-history affordances.",
            "",
            "Suggested first export rule:",
            "",
            "```text",
            "Role layer: Tier A",
            "Visible edge rule: sharedWorksCount >= 2 OR top 10 strongest neighbors per node",
            "Person detail: show Tier A/B/C/CAST first, then Tier D behind load-more",
            "```",
            "",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def _counter_table(values: dict[int | None, int], label: str) -> list[str]:
    lines = [f"| {label} | Count |", "| ---: | ---: |"]
    for key, value in values.items():
        rendered_key = "NULL" if key is None else str(key)
        lines.append(f"| {rendered_key} | {value:,} |")
    return lines


def _single_int(conn: duckdb.DuckDBPyConnection, query: str) -> int:
    return int(conn.execute(query).fetchone()[0])


def _query_table(
    conn: duckdb.DuckDBPyConnection, query: str, headers: tuple[str, ...]
) -> list[str]:
    rows = conn.execute(query).fetchall()
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        rendered: list[str] = []
        for value in row:
            if isinstance(value, int):
                rendered.append(f"{value:,}")
            elif value is None:
                rendered.append("")
            else:
                rendered.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(rendered) + " |")
    return lines


def _layer_section(audit: LayerAudit) -> list[str]:
    lines = [
        f"### {audit.name}",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Subjects | {audit.subjects:,} |",
        f"| Persons | {audit.persons:,} |",
        f"| Credits | {audit.credits:,} |",
        f"| Estimated pair contributions | {audit.estimated_pair_contributions:,} |",
        f"| Max people on one subject | {audit.max_people_on_one_subject:,} |",
    ]
    if audit.max_people_subject_id is not None:
        subject_name = audit.max_people_subject_name.replace("|", "\\|")
        lines.append(
            f"| Max people subject | `{audit.max_people_subject_id}` {subject_name} |"
        )
    if not audit.materialized:
        lines.extend(
            [
                "",
                "Unique edge aggregation was skipped because the estimated pair contribution count exceeded the configured materialization limit.",
                "",
            ]
        )
        return lines

    lines.extend(
        [
            f"| Unique edges | {audit.unique_edges:,} |",
            f"| Nodes with edges | {audit.nodes_with_edges:,} |",
            f"| Edges with `sharedWorksCount >= 2` | {audit.shared_works_ge_2_edges:,} |",
            f"| Degree median | {audit.degree_median:,.1f} |",
            f"| Degree p95 | {audit.degree_p95:,} |",
            f"| Degree max | {audit.degree_max:,} |",
            "",
            "| Strategy | Visible Nodes | Visible Edges |",
            "| --- | ---: | ---: |",
        ]
    )
    for stats in audit.top_k:
        lines.append(
            f"| Top {stats.k} strongest neighbors per node | {stats.node_count:,} | {stats.edge_count:,} |"
        )
    lines.append("")
    return lines
