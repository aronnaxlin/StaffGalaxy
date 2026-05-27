from __future__ import annotations

import argparse
from pathlib import Path

from .archive import detect_archive_zip
from .database import connect_database, create_indexes, create_supporting_views
from .graph_nodes import build_graph_nodes
from .graph_audit import audit_graph_layers
from .ingest import ingest_archive
from .report import write_audit_report
from .roles import detect_staff_constants, load_anime_staff_positions
from .visible_edges import build_visible_person_edges


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
        edge_stats = build_visible_person_edges(conn, role_tier="A", top_k=10)
        node_stats = build_graph_nodes(conn, role_tier="A")
        create_supporting_views(conn)
        create_indexes(conn)
        print(
            f"Visible edges built: {edge_stats.edge_count:,} edges across "
            f"{edge_stats.node_count:,} people.",
            flush=True,
        )
        print(
            f"Graph nodes built: {node_stats.node_count:,} Tier A people "
            f"({node_stats.nodes_with_visible_edges:,} with visible edges).",
            flush=True,
        )
        layer_audits = audit_graph_layers(conn, args.pair_materialize_limit)
        print("Graph audit complete.", flush=True)
        metadata = archive.latest_metadata or {}
        created_at = metadata.get("created_at")
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
