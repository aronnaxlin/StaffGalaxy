"""Export DuckDB graph data to static JSON files for the frontend.

Two-level data architecture:
- L0 (global): top ~260 nodes (degree >= 150) + their inter-edges
- L1 (detail): ~1700 nodes (degree >= 50) + sparse edges (shared >= 3)
"""

import json
import math
import duckdb
from pathlib import Path

DB_PATH = Path("data/processed/staff_galaxy.duckdb")
OUT_DIR = Path("frontend/public/data")

L0_MIN_DEGREE = 150
L1_MIN_DEGREE = 50
L0_MIN_SHARED = 1
L1_MIN_SHARED = 3


def export_nodes(con: duckdb.DuckDBPyConnection, min_degree: int) -> list[dict]:
    rows = con.execute(f"""
        SELECT g.person_id, p.name, g.x, g.y, g.visible_degree
        FROM graph_nodes g JOIN persons p ON g.person_id = p.id
        WHERE g.visible_degree >= {min_degree}
        ORDER BY g.visible_degree DESC
    """).fetchall()

    nodes = []
    for person_id, name, x, y, degree in rows:
        node: dict = {
            "id": str(person_id),
            "name": name,
            "degree": degree,
        }
        if x is not None and not math.isnan(x):
            node["x"] = round(x, 3)
        if y is not None and not math.isnan(y):
            node["y"] = round(y, 3)
        nodes.append(node)
    return nodes


def export_edges(con: duckdb.DuckDBPyConnection, min_degree: int, min_shared: int) -> list[dict]:
    rows = con.execute(f"""
        SELECT e.source_person_id, e.target_person_id, e.shared_works_count
        FROM visible_person_edges e
        JOIN graph_nodes s ON e.source_person_id = s.person_id
        JOIN graph_nodes t ON e.target_person_id = t.person_id
        WHERE s.visible_degree >= {min_degree}
          AND t.visible_degree >= {min_degree}
          AND e.shared_works_count >= {min_shared}
        ORDER BY e.shared_works_count DESC
    """).fetchall()
    return [{"source": str(s), "target": str(t), "w": c} for s, t, c in rows]


def export_search_index(con: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = con.execute("""
        SELECT g.person_id, p.name, g.visible_degree
        FROM graph_nodes g JOIN persons p ON g.person_id = p.id
        ORDER BY g.visible_degree DESC
    """).fetchall()
    return [{"id": str(pid), "name": name, "degree": d} for pid, name, d in rows]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    kb = path.stat().st_size / 1024
    n = len(data) if isinstance(data, list) else ""
    print(f"  {path}  ({kb:.0f} KB, {n} items)")


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)

    print(f"L0 nodes (degree >= {L0_MIN_DEGREE})…")
    l0_nodes = export_nodes(con, L0_MIN_DEGREE)
    write_json(OUT_DIR / "galaxy" / "nodes-l0.json", l0_nodes)

    print(f"L0 edges (shared >= {L0_MIN_SHARED})…")
    l0_edges = export_edges(con, L0_MIN_DEGREE, L0_MIN_SHARED)
    write_json(OUT_DIR / "galaxy" / "edges-l0.json", l0_edges)

    print(f"L1 nodes (degree >= {L1_MIN_DEGREE})…")
    l1_nodes = export_nodes(con, L1_MIN_DEGREE)
    write_json(OUT_DIR / "galaxy" / "nodes-l1.json", l1_nodes)

    print(f"L1 edges (shared >= {L1_MIN_SHARED})…")
    l1_edges = export_edges(con, L1_MIN_DEGREE, L1_MIN_SHARED)
    write_json(OUT_DIR / "galaxy" / "edges-l1.json", l1_edges)

    print("Search index (all)…")
    index = export_search_index(con)
    write_json(OUT_DIR / "search" / "persons-index.json", index)

    manifest = {
        "version": 3,
        "l0_nodes": len(l0_nodes),
        "l0_edges": len(l0_edges),
        "l1_nodes": len(l1_nodes),
        "l1_edges": len(l1_edges),
    }
    write_json(OUT_DIR / "manifest.json", manifest)
    print("Done.")


if __name__ == "__main__":
    main()
