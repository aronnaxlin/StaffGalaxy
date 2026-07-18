from __future__ import annotations

import argparse
from pathlib import Path

from .archive import detect_archive_zip
from .database import connect_database, create_indexes, create_supporting_views, record_data_snapshot
from .graph_nodes import build_graph_nodes
from .graph_audit import audit_graph_layers
from .ingest import ingest_archive
from .layout import build_hierarchical_layout
from .report import write_audit_report
from .search_index import build_person_search_terms
from .roles import detect_staff_constants, load_anime_staff_positions
from .visible_edges import build_person_collaboration_edges, build_visible_person_edges


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Staff Galaxy audit database.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--archive-zip", type=Path)
    parser.add_argument("--staffs-yml", type=Path)
    parser.add_argument("--db", type=Path, default=Path("data/processed/staff_galaxy.duckdb"))
    parser.add_argument("--extract-dir", type=Path, default=Path("data/processed/extracted"))
    parser.add_argument("--report", type=Path, default=Path("reports/data-audit.md"))
    parser.add_argument("--pair-materialize-limit", type=int, default=8_000_000)
    args = parser.parse_args()

    archive = detect_archive_zip(args.raw_dir, args.archive_zip)
    staffs_yml = detect_staff_constants(args.raw_dir, args.staffs_yml)
    positions = load_anime_staff_positions(staffs_yml)

    print(f"Using archive: {archive.zip_path}", flush=True)
    print(f"Using staff constants: {staffs_yml}", flush=True)
    print(f"Writing database: {args.db}", flush=True)

    conn = connect_database(args.db)
    try:
        ingest_stats = ingest_archive(conn, archive, positions, args.extract_dir)
        print("Ingest complete.", flush=True)
        collaboration_stats = build_person_collaboration_edges(conn)
        edge_stats = build_visible_person_edges(conn, min_role_weight=12.0, top_k=10)
        node_stats = build_graph_nodes(conn, min_role_weight=12.0)
        layout_stats = build_hierarchical_layout(conn)
        search_stats = build_person_search_terms(conn)
        create_supporting_views(conn)
        create_indexes(conn)
        metadata = archive.latest_metadata or {}
        created_at = metadata.get("created_at")
        source_url = metadata.get("browser_download_url")
        record_data_snapshot(
            conn,
            archive_name=archive.zip_path.name,
            archive_created_at=created_at if isinstance(created_at, str) else "",
            archive_size_bytes=archive.zip_path.stat().st_size,
            source_url=source_url if isinstance(source_url, str) else "",
        )
        print(
            f"Complete staff collaboration edges built: {collaboration_stats.edge_count:,} edges "
            f"across {collaboration_stats.node_count:,} people.",
            flush=True,
        )
        print(
            f"Visible edges built: {edge_stats.edge_count:,} edges across "
            f"{edge_stats.node_count:,} people (weight >= 12).",
            flush=True,
        )
        print(
            f"Graph nodes built: {node_stats.node_count:,} people "
            f"({node_stats.nodes_with_visible_edges:,} with visible edges).",
            flush=True,
        )
        print(
            f"Layout {layout_stats.layout_method}: {layout_stats.community_count:,} communities "
            f"(largest {layout_stats.largest_community_size:,}), "
            f"{layout_stats.isolated_node_count:,} isolates, {layout_stats.elapsed_seconds}s.",
            flush=True,
        )
        print(
            f"Search index built: {search_stats.term_count:,} terms across "
            f"{search_stats.person_count:,} people.",
            flush=True,
        )
        layer_audits = audit_graph_layers(conn, args.pair_materialize_limit)
        print("Graph audit complete.", flush=True)
        write_audit_report(
            path=args.report,
            conn=conn,
            archive_name=archive.zip_path.name,
            archive_created_at=created_at if isinstance(created_at, str) else "",
            archive_size_bytes=archive.zip_path.stat().st_size,
            ingest_stats=ingest_stats,
            layer_audits=layer_audits,
        )
        print(f"Wrote report: {args.report}", flush=True)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
