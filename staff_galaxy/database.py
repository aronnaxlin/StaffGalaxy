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
    conn.execute("DROP TABLE IF EXISTS visible_person_edges")
    conn.execute("DROP TABLE IF EXISTS graph_nodes")
    conn.execute("DROP VIEW IF EXISTS credit_details")
    conn.execute("DROP VIEW IF EXISTS cast_details")
    conn.execute("DROP VIEW IF EXISTS anime_participation_details")
    conn.execute("DROP VIEW IF EXISTS person_role_counts")
    conn.execute("DROP VIEW IF EXISTS person_anime_stats")
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


def create_supporting_views(conn: duckdb.DuckDBPyConnection) -> None:
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
          COUNT(*) FILTER (WHERE c.role_tier = 'A') AS tier_a_credit_count,
          COUNT(*) FILTER (WHERE c.role_tier = 'B') AS tier_b_credit_count,
          COUNT(*) FILTER (WHERE c.role_tier = 'C') AS tier_c_credit_count,
          COUNT(*) FILTER (WHERE c.role_tier = 'D') AS tier_d_credit_count,
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_credits_person ON credits(person_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_credits_subject ON credits(subject_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_credits_role_tier ON credits(role_tier)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_characters_person ON person_characters(person_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_characters_subject ON person_characters(subject_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visible_edges_source ON visible_person_edges(source_person_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visible_edges_target ON visible_person_edges(target_person_id)"
    )
