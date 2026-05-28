from __future__ import annotations

from pathlib import Path

import duckdb


def connect_database(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("DROP TABLE IF EXISTS subjects")
    conn.execute("DROP TABLE IF EXISTS persons")
    conn.execute("DROP TABLE IF EXISTS characters")
    conn.execute("DROP TABLE IF EXISTS credits")
    conn.execute("DROP TABLE IF EXISTS person_characters")
    conn.execute("DROP TABLE IF EXISTS staff_positions")
    conn.execute("DROP TABLE IF EXISTS person_collaboration_edges")
    conn.execute("DROP TABLE IF EXISTS visible_person_edges")
    conn.execute("DROP TABLE IF EXISTS graph_nodes")
    conn.execute("DROP TABLE IF EXISTS person_search_terms")
    conn.execute("DROP TABLE IF EXISTS data_snapshots")
    conn.execute("DROP VIEW IF EXISTS credit_details")
    conn.execute("DROP VIEW IF EXISTS cast_details")
    conn.execute("DROP VIEW IF EXISTS anime_participation_details")
    conn.execute("DROP VIEW IF EXISTS person_role_counts")
    conn.execute("DROP VIEW IF EXISTS person_anime_stats")
    conn.execute("DROP VIEW IF EXISTS person_collaboration_edge_details")
    conn.execute("DROP VIEW IF EXISTS visible_edge_details")

    conn.execute(
        """
        CREATE TABLE subjects (
          id INTEGER PRIMARY KEY,
          type INTEGER,
          name TEXT,
          name_cn TEXT,
          date TEXT,
          year INTEGER,
          platform INTEGER,
          score DOUBLE,
          rank INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE persons (
          id INTEGER PRIMARY KEY,
          name TEXT,
          type INTEGER,
          infobox TEXT,
          career_json TEXT,
          summary TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE characters (
          id INTEGER PRIMARY KEY,
          name TEXT,
          role INTEGER,
          summary TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE staff_positions (
          position_id INTEGER PRIMARY KEY,
          cn TEXT,
          en TEXT,
          jp TEXT,
          normalized_role TEXT,
          role_tier TEXT,
          role_weight DOUBLE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE credits (
          subject_id INTEGER,
          person_id INTEGER,
          position_id INTEGER,
          raw_position TEXT,
          position_cn TEXT,
          position_en TEXT,
          position_jp TEXT,
          normalized_role TEXT,
          role_tier TEXT,
          role_weight DOUBLE,
          appear_eps TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE person_characters (
          subject_id INTEGER,
          person_id INTEGER,
          character_id INTEGER,
          character_name TEXT,
          character_role INTEGER,
          person_character_type INTEGER,
          summary TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE person_collaboration_edges (
          source_person_id INTEGER,
          target_person_id INTEGER,
          shared_works_count INTEGER,
          collaboration_score DOUBLE,
          first_year INTEGER,
          last_year INTEGER,
          role_layer TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE visible_person_edges (
          source_person_id INTEGER,
          target_person_id INTEGER,
          shared_works_count INTEGER,
          collaboration_score DOUBLE,
          first_year INTEGER,
          last_year INTEGER,
          role_layer TEXT,
          top_neighbor_rank INTEGER,
          selection_reason TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE graph_nodes (
          person_id INTEGER PRIMARY KEY,
          community_id INTEGER,
          x DOUBLE,
          y DOUBLE,
          visible_degree INTEGER,
          visible_weighted_degree DOUBLE,
          node_size DOUBLE,
          role_layer TEXT,
          layout_method TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE data_snapshots (
          snapshot_id TEXT PRIMARY KEY,
          archive_name TEXT,
          archive_created_at TEXT,
          archive_size_bytes BIGINT,
          built_at TIMESTAMP,
          source_url TEXT
        )
        """
    )


def ensure_credits_raw_position(conn: duckdb.DuckDBPyConnection) -> None:
    """Add raw position storage for older local databases."""
    columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info('credits')").fetchall()
    }
    if "raw_position" not in columns:
        conn.execute("ALTER TABLE credits ADD COLUMN raw_position TEXT")
    conn.execute(
        """
        UPDATE credits
        SET raw_position = position_cn
        WHERE raw_position IS NULL OR raw_position = ''
        """
    )


def ensure_person_infobox(conn: duckdb.DuckDBPyConnection) -> None:
    """Add raw infobox storage for older local databases."""
    columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info('persons')").fetchall()
    }
    if "infobox" not in columns:
        conn.execute("ALTER TABLE persons ADD COLUMN infobox TEXT")
    conn.execute(
        """
        UPDATE persons
        SET infobox = ''
        WHERE infobox IS NULL
        """
    )


def ensure_data_snapshots(conn: duckdb.DuckDBPyConnection) -> None:
    """Add data snapshot metadata for older local databases."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS data_snapshots (
          snapshot_id TEXT PRIMARY KEY,
          archive_name TEXT,
          archive_created_at TEXT,
          archive_size_bytes BIGINT,
          built_at TIMESTAMP,
          source_url TEXT
        )
        """
    )


def record_data_snapshot(
    conn: duckdb.DuckDBPyConnection,
    *,
    archive_name: str,
    archive_created_at: str,
    archive_size_bytes: int,
    source_url: str,
) -> None:
    ensure_data_snapshots(conn)
    conn.execute("DELETE FROM data_snapshots WHERE snapshot_id = 'current'")
    conn.execute(
        """
        INSERT INTO data_snapshots (
          snapshot_id,
          archive_name,
          archive_created_at,
          archive_size_bytes,
          built_at,
          source_url
        )
        VALUES ('current', ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """,
        [archive_name, archive_created_at, archive_size_bytes, source_url],
    )


def create_supporting_views(conn: duckdb.DuckDBPyConnection) -> None:
    ensure_credits_raw_position(conn)
    ensure_person_infobox(conn)
    ensure_data_snapshots(conn)

    conn.execute(
        """
        CREATE OR REPLACE VIEW credit_details AS
        SELECT
          c.subject_id,
          s.name AS subject_name,
          s.name_cn AS subject_name_cn,
          s.date AS subject_date,
          s.year AS subject_year,
          c.person_id,
          p.name AS person_name,
          c.position_id,
          c.raw_position,
          c.position_cn,
          c.position_en,
          c.position_jp,
          c.normalized_role,
          c.role_tier,
          c.role_weight,
          c.appear_eps
        FROM credits c
        JOIN subjects s ON s.id = c.subject_id
        JOIN persons p ON p.id = c.person_id
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE VIEW cast_details AS
        SELECT
          pc.subject_id,
          s.name AS subject_name,
          s.name_cn AS subject_name_cn,
          s.date AS subject_date,
          s.year AS subject_year,
          pc.person_id,
          p.name AS person_name,
          pc.character_id,
          pc.character_name,
          pc.character_role,
          pc.person_character_type,
          pc.summary
        FROM person_characters pc
        JOIN subjects s ON s.id = pc.subject_id
        JOIN persons p ON p.id = pc.person_id
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE VIEW anime_participation_details AS
        SELECT
          subject_id,
          subject_name,
          subject_name_cn,
          subject_date,
          subject_year,
          person_id,
          person_name,
          'staff' AS participation_type,
          position_cn AS role_label,
          raw_position,
          normalized_role,
          role_tier,
          NULL::INTEGER AS character_id,
          NULL::TEXT AS character_name
        FROM credit_details
        UNION ALL
        SELECT
          subject_id,
          subject_name,
          subject_name_cn,
          subject_date,
          subject_year,
          person_id,
          person_name,
          'cast' AS participation_type,
          '配音' AS role_label,
          NULL::TEXT AS raw_position,
          'voice_cast' AS normalized_role,
          'CAST' AS role_tier,
          character_id,
          character_name
        FROM cast_details
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE VIEW person_role_counts AS
        SELECT
          person_id,
          person_name,
          position_id,
          position_cn,
          normalized_role,
          role_tier,
          COUNT(*) AS credit_count
        FROM credit_details
        GROUP BY
          person_id,
          person_name,
          position_id,
          position_cn,
          normalized_role,
          role_tier
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE VIEW person_anime_stats AS
        SELECT
          p.id AS person_id,
          p.name AS person_name,
          p.career_json,
          COUNT(c.*) AS anime_credit_count,
          COUNT(DISTINCT c.subject_id) AS anime_subject_count,
          COUNT(*) FILTER (WHERE c.role_tier = 'S') AS tier_s_credit_count,
          COUNT(*) FILTER (WHERE c.role_tier = 'A') AS tier_a_credit_count,
          COUNT(*) FILTER (WHERE c.role_tier = 'B') AS tier_b_credit_count,
          COUNT(*) FILTER (WHERE c.role_tier = 'C') AS tier_c_credit_count,
          COUNT(*) FILTER (WHERE c.role_tier = 'D') AS tier_d_credit_count,
          COUNT(*) FILTER (WHERE c.role_tier IN ('E', 'F')) AS tier_ef_credit_count,
          MIN(s.year) AS first_credit_year,
          MAX(s.year) AS latest_credit_year
        FROM persons p
        JOIN credits c ON c.person_id = p.id
        JOIN subjects s ON s.id = c.subject_id
        GROUP BY p.id, p.name, p.career_json
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE VIEW person_collaboration_edge_details AS
        SELECT
          e.source_person_id,
          ps.name AS source_person_name,
          e.target_person_id,
          pt.name AS target_person_name,
          e.shared_works_count,
          e.collaboration_score,
          e.first_year,
          e.last_year,
          e.role_layer
        FROM person_collaboration_edges e
        JOIN persons ps ON ps.id = e.source_person_id
        JOIN persons pt ON pt.id = e.target_person_id
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE VIEW visible_edge_details AS
        SELECT
          e.source_person_id,
          ps.name AS source_person_name,
          e.target_person_id,
          pt.name AS target_person_name,
          e.shared_works_count,
          e.collaboration_score,
          e.first_year,
          e.last_year,
          e.role_layer,
          e.top_neighbor_rank,
          e.selection_reason
        FROM visible_person_edges e
        JOIN persons ps ON ps.id = e.source_person_id
        JOIN persons pt ON pt.id = e.target_person_id
        """
    )


def create_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subjects_type ON subjects(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_search_terms_person ON person_search_terms(person_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_search_terms_norm ON person_search_terms(term_norm)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_search_terms_compact ON person_search_terms(term_compact)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_credits_person ON credits(person_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_credits_subject ON credits(subject_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_credits_role_tier ON credits(role_tier)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_characters_person ON person_characters(person_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_characters_subject ON person_characters(subject_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_collaboration_edges_source ON person_collaboration_edges(source_person_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_collaboration_edges_target ON person_collaboration_edges(target_person_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visible_edges_source ON visible_person_edges(source_person_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visible_edges_target ON visible_person_edges(target_person_id)"
    )
