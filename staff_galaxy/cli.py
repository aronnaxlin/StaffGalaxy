from __future__ import annotations

import argparse
from pathlib import Path

from neo4j import Driver

from .archive import detect_archive_zip
from .graph_audit import audit_graph_layers
from .graph_db import connect_driver, connection_uri, record_data_snapshot
from .graph_nodes import build_graph_nodes
from .ingest import ingest_archive
from .layout import build_hierarchical_layout
from .report import write_audit_report
from .roles import detect_staff_constants, load_anime_staff_positions
from .search_index import build_person_search_terms
from .visible_edges import build_visible_person_edges


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Staff Galaxy Neo4j knowledge graph.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--archive-zip", type=Path)
    parser.add_argument("--staffs-yml", type=Path)
    parser.add_argument("--report", type=Path, default=Path("reports/data-audit.md"))
    parser.add_argument("--pair-materialize-limit", type=int, default=8_000_000)
    parser.add_argument(
        "--derived-only",
        action="store_true",
        help="Keep the ingested graph; rebuild COLLAB edges, galaxy nodes, layout, and search terms.",
    )
    args = parser.parse_args()

    print(f"Writing Neo4j graph: {connection_uri()}", flush=True)
    driver = connect_driver()
    try:
        driver.verify_connectivity()
        if args.derived_only:
            build_derived_graph(driver)
            return 0

        archive = detect_archive_zip(args.raw_dir, args.archive_zip)
        staffs_yml = detect_staff_constants(args.raw_dir, args.staffs_yml)
        positions = load_anime_staff_positions(staffs_yml)
        print(f"Using archive: {archive.zip_path}", flush=True)
        print(f"Using staff constants: {staffs_yml}", flush=True)

        ingest_stats = ingest_archive(driver, archive, positions)
        print("Ingest complete.", flush=True)
        build_derived_graph(driver)

        metadata = archive.latest_metadata or {}
        created_at = metadata.get("created_at")
        source_url = metadata.get("browser_download_url")
        record_data_snapshot(
            driver,
            archive_name=archive.zip_path.name,
            archive_created_at=created_at if isinstance(created_at, str) else "",
            archive_size_bytes=archive.zip_path.stat().st_size,
            source_url=source_url if isinstance(source_url, str) else "",
        )
        layer_audits = audit_graph_layers(driver, args.pair_materialize_limit)
        print("Graph audit complete.", flush=True)
        write_audit_report(
            path=args.report,
            driver=driver,
            archive_name=archive.zip_path.name,
            archive_created_at=created_at if isinstance(created_at, str) else "",
            archive_size_bytes=archive.zip_path.stat().st_size,
            ingest_stats=ingest_stats,
            layer_audits=layer_audits,
        )
        print(f"Wrote report: {args.report}", flush=True)
    finally:
        driver.close()
    return 0


def build_derived_graph(driver: Driver) -> None:
    edge_stats = build_visible_person_edges(driver, min_role_weight=12.0)
    print(
        f"Visible COLLAB edges built: {edge_stats.edge_count:,} of {edge_stats.candidate_edge_count:,} "
        f"candidates across {edge_stats.node_count:,} people (weight >= 12): "
        f"{edge_stats.significant_edges:,} BiCM-significant at FDR {edge_stats.fdr_q} "
        f"({edge_stats.people_with_significant_edges:,} people), "
        f"{edge_stats.spanning_forest_edges:,} spanning-forest.",
        flush=True,
    )
    node_stats = build_graph_nodes(driver, min_role_weight=12.0)
    print(
        f"Galaxy nodes built: {node_stats.node_count:,} people "
        f"({node_stats.nodes_with_visible_edges:,} with visible edges).",
        flush=True,
    )
    layout_stats = build_hierarchical_layout(driver)
    print(
        f"Layout {layout_stats.layout_method}: {layout_stats.community_count:,} communities "
        f"(largest {layout_stats.largest_community_size:,}), "
        f"{layout_stats.isolated_node_count:,} isolates, {layout_stats.elapsed_seconds}s.",
        flush=True,
    )
    search_stats = build_person_search_terms(driver)
    print(
        f"Search index built: {search_stats.term_count:,} terms across "
        f"{search_stats.person_count:,} people.",
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
