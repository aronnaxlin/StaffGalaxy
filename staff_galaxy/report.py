from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from neo4j import Driver

from .graph_audit import LayerAudit
from .graph_db import read, read_one
from .ingest import IngestStats


def write_audit_report(
    path: Path,
    driver: Driver,
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
            f"| Anime cast rows involving real individual people | {ingest_stats.anime_cast_rows:,} |",
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
        driver,
        """
        MATCH ()-[c:CREDITED]->()
        RETURN c.position_id AS position_id, c.position_cn AS cn, c.position_en AS en,
               count(*) AS credit_count
        ORDER BY credit_count DESC, position_id
        LIMIT 40
        """,
        ("Position ID", "CN", "EN", "Credits"),
    ))

    lines.extend(["", "## Top Cast People By Anime Character Links", ""])
    lines.extend(_query_table(
        driver,
        """
        MATCH (p:Person)-[v:VOICED]->()
        RETURN p.name AS person_name, count(v) AS cast_rows
        ORDER BY cast_rows DESC, person_name
        LIMIT 20
        """,
        ("Person", "Cast Rows"),
    ))

    lines.extend(["", "## Normalized Role Counts", ""])
    lines.extend(_query_table(
        driver,
        """
        MATCH ()-[c:CREDITED]->()
        WHERE c.normalized_role IS NOT NULL
        RETURN c.normalized_role AS role, c.role_tier AS tier, count(*) AS credit_count
        ORDER BY credit_count DESC, role
        """,
        ("Role", "Tier", "Credits"),
    ))

    unmapped = _single_int(
        driver, "MATCH ()-[c:CREDITED]->() WHERE c.normalized_role IS NULL RETURN count(c) AS n"
    )
    tier_d = _single_int(
        driver, "MATCH ()-[c:CREDITED]->() WHERE c.role_tier = 'D' RETURN count(c) AS n"
    )
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
        driver,
        """
        MATCH ()-[c:CREDITED]->()
        WHERE c.role_tier = 'D'
        RETURN c.position_id AS position_id, c.position_cn AS cn, c.position_en AS en,
               count(*) AS credit_count
        ORDER BY credit_count DESC, position_id
        LIMIT 30
        """,
        ("Position ID", "CN", "EN", "Credits"),
    ))

    lines.extend(["", "## Candidate Graph Scale", ""])
    for audit in layer_audits:
        lines.extend(_layer_section(audit))

    visible_summary = read_one(
        driver,
        """
        MATCH (s:Person)-[e:COLLAB]->(t:Person)
        WITH collect(DISTINCT s.id) + collect(DISTINCT t.id) AS endpoints,
             count(e) AS edge_count,
             count(CASE WHEN e.shared_works_count >= 2 THEN 1 END) AS shared_ge_2,
             count(CASE WHEN e.selection_reason = 'bicm_significant' THEN 1 END) AS significant,
             count(CASE WHEN e.selection_reason = 'spanning_forest' THEN 1 END) AS forest
        UNWIND endpoints AS person_id
        RETURN edge_count, shared_ge_2, significant, forest, count(DISTINCT person_id) AS visible_nodes
        """,
    ) or {"edge_count": 0, "shared_ge_2": 0, "significant": 0, "forest": 0, "visible_nodes": 0}
    lines.extend(
        [
            "",
            "## Built Visible Backbone",
            "",
            "The galaxy backbone is the BiCM-validated projection of the weight >= 12 person-anime layer "
            "(Benjamini-Hochberg FDR 0.05 over all person pairs), united with the maximum spanning forest "
            "by collaboration score so no person is stranded. See `staff_galaxy/visible_edges.py`.",
            "",
            "| Metric | Count |",
            "| --- | ---: |",
            f"| Visible nodes | {visible_summary['visible_nodes']:,} |",
            f"| Visible edges | {visible_summary['edge_count']:,} |",
            f"| Edges with `sharedWorksCount >= 2` | {visible_summary['shared_ge_2']:,} |",
            f"| BiCM-significant edges | {visible_summary['significant']:,} |",
            f"| Spanning-forest-only edges | {visible_summary['forest']:,} |",
            "",
        ]
    )
    graph_node_summary = read_one(
        driver,
        """
        MATCH (g:GalaxyNode)
        RETURN count(g) AS node_count,
               count(CASE WHEN g.visible_degree > 0 THEN 1 END) AS nodes_with_edges,
               coalesce(max(g.visible_degree), 0) AS max_degree,
               round(coalesce(max(g.node_size), 0.0), 2) AS max_size,
               min(g.layout_method) AS layout_method
        """,
    ) or {}
    lines.extend(
        [
            "## Built Graph Nodes",
            "",
            "The database labels galaxy members as `:GalaxyNode` and stores their layout coordinates on the node.",
            "",
            "| Metric | Count |",
            "| --- | ---: |",
            f"| Graph nodes | {graph_node_summary.get('node_count', 0):,} |",
            f"| Nodes with visible edges | {graph_node_summary.get('nodes_with_edges', 0):,} |",
            f"| Max visible degree | {graph_node_summary.get('max_degree', 0):,} |",
            f"| Max node size | {graph_node_summary.get('max_size', 0.0)} |",
            f"| Layout method | `{graph_node_summary.get('layout_method')}` |",
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


def _single_int(driver: Driver, query: str) -> int:
    row = read_one(driver, query)
    return int(next(iter(row.values()))) if row else 0


def _query_table(driver: Driver, query: str, headers: tuple[str, ...]) -> list[str]:
    rows: list[tuple[Any, ...]] = [tuple(row.values()) for row in read(driver, query)]
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
