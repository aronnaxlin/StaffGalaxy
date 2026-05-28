from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

import duckdb

from .archive import ArchiveInput
from .database import create_schema
from .roles import StaffPosition, role_definition_for


REQUIRED_EXTRACT_MEMBERS = (
    "subject.jsonlines",
    "person.jsonlines",
    "character.jsonlines",
    "subject-persons.jsonlines",
    "person-characters.jsonlines",
)


@dataclass(frozen=True)
class IngestStats:
    subject_count_by_type: dict[int | None, int]
    person_count_by_type: dict[int | None, int]
    anime_subject_count: int
    real_person_count: int
    subject_person_rows_total: int
    anime_real_person_credits: int
    real_people_with_anime_credits: int
    anime_subjects_with_real_person_credits: int


def ingest_archive(
    conn: duckdb.DuckDBPyConnection,
    archive: ArchiveInput,
    positions: dict[int, StaffPosition],
    extract_root: Path,
) -> IngestStats:
    create_schema(conn)
    _insert_staff_positions(conn, positions)

    extracted_dir = extract_required_members(archive.zip_path, extract_root)
    subject_path = extracted_dir / "subject.jsonlines"
    person_path = extracted_dir / "person.jsonlines"
    character_path = extracted_dir / "character.jsonlines"
    subject_persons_path = extracted_dir / "subject-persons.jsonlines"
    person_characters_path = extracted_dir / "person-characters.jsonlines"

    conn.execute(
        f"""
        INSERT INTO subjects
        SELECT
          id::INTEGER AS id,
          type::INTEGER AS type,
          COALESCE(name, '') AS name,
          COALESCE(name_cn, '') AS name_cn,
          COALESCE(date, '') AS date,
          TRY_CAST(SUBSTRING(COALESCE(date, ''), 1, 4) AS INTEGER) AS year,
          platform::INTEGER AS platform,
          score::DOUBLE AS score,
          rank::INTEGER AS rank
        FROM read_json(
          {_sql_string(subject_path)},
          format = 'newline_delimited',
          columns = {{
            id: 'INTEGER',
            type: 'INTEGER',
            name: 'VARCHAR',
            name_cn: 'VARCHAR',
            date: 'VARCHAR',
            platform: 'INTEGER',
            score: 'DOUBLE',
            rank: 'INTEGER'
          }}
        )
        """
    )

    conn.execute(
        f"""
        INSERT INTO persons
        SELECT
          id::INTEGER AS id,
          COALESCE(name, '') AS name,
          type::INTEGER AS type,
          COALESCE(infobox, '') AS infobox,
          COALESCE(CAST(career AS VARCHAR), '') AS career_json,
          COALESCE(summary, '') AS summary
        FROM read_json(
          {_sql_string(person_path)},
          format = 'newline_delimited',
          columns = {{
            id: 'INTEGER',
            name: 'VARCHAR',
            type: 'INTEGER',
            infobox: 'VARCHAR',
            career: 'JSON',
            summary: 'VARCHAR'
          }}
        )
        """
    )

    conn.execute(
        f"""
        INSERT INTO characters
        SELECT
          id::INTEGER AS id,
          COALESCE(name, '') AS name,
          role::INTEGER AS role,
          COALESCE(summary, '') AS summary
        FROM read_json(
          {_sql_string(character_path)},
          format = 'newline_delimited',
          columns = {{
            id: 'INTEGER',
            role: 'INTEGER',
            name: 'VARCHAR',
            summary: 'VARCHAR'
          }}
        )
        """
    )

    conn.execute(
        f"""
        CREATE TEMP VIEW subject_persons_raw AS
        SELECT
          subject_id::INTEGER AS subject_id,
          person_id::INTEGER AS person_id,
          position::INTEGER AS position_id,
          COALESCE(appear_eps, '') AS appear_eps
        FROM read_json(
          {_sql_string(subject_persons_path)},
          format = 'newline_delimited',
          columns = {{
            subject_id: 'INTEGER',
            person_id: 'INTEGER',
            position: 'INTEGER',
            appear_eps: 'VARCHAR'
          }}
        )
        """
    )

    conn.execute(
        """
        INSERT INTO credits
        SELECT DISTINCT
          sp.subject_id,
          sp.person_id,
          sp.position_id,
          COALESCE(pos.cn, '') AS raw_position,
          COALESCE(pos.cn, '') AS position_cn,
          COALESCE(pos.en, '') AS position_en,
          COALESCE(pos.jp, '') AS position_jp,
          COALESCE(pos.normalized_role, 'unknown_position_' || CAST(sp.position_id AS VARCHAR)),
          COALESCE(pos.role_tier, 'D'),
          COALESCE(pos.role_weight, 0.25),
          sp.appear_eps
        FROM subject_persons_raw sp
        JOIN subjects s ON s.id = sp.subject_id AND s.type = 2
        JOIN persons p ON p.id = sp.person_id AND p.type = 1
        LEFT JOIN staff_positions pos ON pos.position_id = sp.position_id
        """
    )

    conn.execute(
        f"""
        CREATE TEMP VIEW person_characters_raw AS
        SELECT
          subject_id::INTEGER AS subject_id,
          person_id::INTEGER AS person_id,
          character_id::INTEGER AS character_id,
          type::INTEGER AS person_character_type,
          COALESCE(summary, '') AS summary
        FROM read_json(
          {_sql_string(person_characters_path)},
          format = 'newline_delimited',
          columns = {{
            subject_id: 'INTEGER',
            person_id: 'INTEGER',
            character_id: 'INTEGER',
            type: 'INTEGER',
            summary: 'VARCHAR'
          }}
        )
        """
    )

    conn.execute(
        """
        INSERT INTO person_characters
        SELECT DISTINCT
          pc.subject_id,
          pc.person_id,
          pc.character_id,
          COALESCE(c.name, '') AS character_name,
          c.role AS character_role,
          pc.person_character_type,
          pc.summary
        FROM person_characters_raw pc
        JOIN subjects s ON s.id = pc.subject_id AND s.type = 2
        JOIN persons p ON p.id = pc.person_id AND p.type = 1
        LEFT JOIN characters c ON c.id = pc.character_id
        """
    )

    return _collect_ingest_stats(conn)


def extract_required_members(zip_path: Path, extract_root: Path) -> Path:
    target_dir = extract_root / zip_path.stem
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        missing = sorted(set(REQUIRED_EXTRACT_MEMBERS) - names)
        if missing:
            raise ValueError(
                f"Archive zip {zip_path} is missing required files: {', '.join(missing)}"
            )
        for member in REQUIRED_EXTRACT_MEMBERS:
            target = target_dir / member
            info = archive.getinfo(member)
            if target.exists() and target.stat().st_size == info.file_size:
                continue
            archive.extract(member, target_dir)
    return target_dir


def _insert_staff_positions(
    conn: duckdb.DuckDBPyConnection, positions: dict[int, StaffPosition]
) -> None:
    rows: list[tuple[object, ...]] = []
    for position_id, position in sorted(positions.items()):
        role = role_definition_for(position)
        rows.append(
            (
                position_id,
                position.cn,
                position.en,
                position.jp,
                role.normalized_role,
                role.role_tier,
                role.role_weight,
            )
        )
    conn.executemany(
        """
        INSERT INTO staff_positions (
          position_id, cn, en, jp, normalized_role, role_tier, role_weight
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def _collect_ingest_stats(conn: duckdb.DuckDBPyConnection) -> IngestStats:
    return IngestStats(
        subject_count_by_type=_count_by(conn, "subjects", "type"),
        person_count_by_type=_count_by(conn, "persons", "type"),
        anime_subject_count=_single_int(
            conn, "SELECT COUNT(*) FROM subjects WHERE type = 2"
        ),
        real_person_count=_single_int(conn, "SELECT COUNT(*) FROM persons WHERE type = 1"),
        subject_person_rows_total=_single_int(
            conn, "SELECT COUNT(*) FROM subject_persons_raw"
        ),
        anime_real_person_credits=_single_int(conn, "SELECT COUNT(*) FROM credits"),
        real_people_with_anime_credits=_single_int(
            conn, "SELECT COUNT(DISTINCT person_id) FROM credits"
        ),
        anime_subjects_with_real_person_credits=_single_int(
            conn, "SELECT COUNT(DISTINCT subject_id) FROM credits"
        ),
    )


def _count_by(
    conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str
) -> dict[int | None, int]:
    rows = conn.execute(
        f"""
        SELECT {column_name}, COUNT(*) AS count
        FROM {table_name}
        GROUP BY {column_name}
        ORDER BY {column_name} NULLS FIRST
        """
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _single_int(conn: duckdb.DuckDBPyConnection, query: str) -> int:
    value = conn.execute(query).fetchone()[0]
    return int(value)


def _sql_string(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"
