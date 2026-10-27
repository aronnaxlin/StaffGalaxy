from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from neo4j import Driver

from .archive import ArchiveInput, iter_jsonlines
from .graph_db import clear_database, create_constraints, write_batches
from .roles import StaffPosition, role_definition_for


ANIME_SUBJECT_TYPE = 2
REAL_PERSON_TYPE = 1


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
    anime_cast_rows: int


def ingest_archive(
    driver: Driver,
    archive: ArchiveInput,
    positions: dict[int, StaffPosition],
) -> IngestStats:
    """Rebuild the knowledge graph from an Archive zip (anime + real people only)."""
    clear_database(driver)
    create_constraints(driver)
    position_rows = staff_position_rows(positions)
    write_positions(driver, position_rows)

    subject_counts: Counter[int | None] = Counter()
    anime_rows: list[dict[str, Any]] = []
    for record in iter_jsonlines(archive.zip_path, "subject.jsonlines"):
        subject_type = _int_or_none(record.get("type"))
        subject_counts[subject_type] += 1
        if subject_type == ANIME_SUBJECT_TYPE:
            anime_rows.append(anime_row(record))
    write_anime(driver, anime_rows)
    anime_ids = {row["id"] for row in anime_rows}
    print(f"  Anime nodes: {len(anime_rows):,}", flush=True)

    person_counts: Counter[int | None] = Counter()
    person_rows: list[dict[str, Any]] = []
    for record in iter_jsonlines(archive.zip_path, "person.jsonlines"):
        person_type = _int_or_none(record.get("type"))
        person_counts[person_type] += 1
        if person_type == REAL_PERSON_TYPE:
            person_rows.append(person_row(record))
    write_persons(driver, person_rows)
    person_ids = {row["id"] for row in person_rows}
    print(f"  Person nodes: {len(person_rows):,}", flush=True)

    positions_by_id = {row["position_id"]: row for row in position_rows}
    subject_person_rows_total = 0
    seen_credits: set[tuple[int, int, int, str]] = set()
    credit_rows: list[dict[str, Any]] = []
    for record in iter_jsonlines(archive.zip_path, "subject-persons.jsonlines"):
        subject_person_rows_total += 1
        subject_id = int(record["subject_id"])
        person_id = int(record["person_id"])
        if subject_id not in anime_ids or person_id not in person_ids:
            continue
        position_id = int(record["position"])
        appear_eps = str(record.get("appear_eps") or "")
        key = (subject_id, person_id, position_id, appear_eps)
        if key in seen_credits:
            continue
        seen_credits.add(key)
        credit_rows.append(
            credit_row(subject_id, person_id, position_id, appear_eps, positions_by_id)
        )
    write_credits(driver, credit_rows)
    print(f"  CREDITED relationships: {len(credit_rows):,}", flush=True)

    seen_cast: set[tuple[int, int, int]] = set()
    cast_rows: list[dict[str, Any]] = []
    for record in iter_jsonlines(archive.zip_path, "person-characters.jsonlines"):
        subject_id = int(record["subject_id"])
        person_id = int(record["person_id"])
        if subject_id not in anime_ids or person_id not in person_ids:
            continue
        character_id = int(record["character_id"])
        key = (subject_id, person_id, character_id)
        if key in seen_cast:
            continue
        seen_cast.add(key)
        cast_rows.append(
            {
                "subject_id": subject_id,
                "person_id": person_id,
                "character_id": character_id,
                "person_character_type": _int_or_none(record.get("type")),
                "summary": str(record.get("summary") or ""),
            }
        )

    character_ids = {row["character_id"] for row in cast_rows}
    character_rows = [
        character_row(record)
        for record in iter_jsonlines(archive.zip_path, "character.jsonlines")
        if int(record["id"]) in character_ids
    ]
    # Cast rows can reference characters missing from character.jsonlines; keep
    # them as bare nodes so the VOICED evidence is not dropped.
    known_character_ids = {row["id"] for row in character_rows}
    character_rows.extend(
        {"id": character_id, "name": "", "role": None, "summary": ""}
        for character_id in sorted(character_ids - known_character_ids)
    )
    write_characters(driver, character_rows)
    write_cast(driver, cast_rows)
    print(
        f"  Character nodes: {len(character_rows):,}; VOICED relationships: {len(cast_rows):,}",
        flush=True,
    )

    return IngestStats(
        subject_count_by_type=dict(sorted(subject_counts.items(), key=_null_first)),
        person_count_by_type=dict(sorted(person_counts.items(), key=_null_first)),
        anime_subject_count=len(anime_rows),
        real_person_count=len(person_rows),
        subject_person_rows_total=subject_person_rows_total,
        anime_real_person_credits=len(credit_rows),
        real_people_with_anime_credits=len({row["person_id"] for row in credit_rows}),
        anime_subjects_with_real_person_credits=len({row["subject_id"] for row in credit_rows}),
        anime_cast_rows=len(cast_rows),
    )


# --- Row builders ------------------------------------------------------------


def staff_position_rows(positions: dict[int, StaffPosition]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position_id, position in sorted(positions.items()):
        role = role_definition_for(position)
        rows.append(
            {
                "position_id": position_id,
                "cn": position.cn,
                "en": position.en,
                "jp": position.jp,
                "normalized_role": role.normalized_role,
                "role_tier": role.role_tier,
                "role_weight": role.role_weight,
            }
        )
    return rows


def anime_row(record: dict[str, Any]) -> dict[str, Any]:
    date = str(record.get("date") or "")
    return {
        "id": int(record["id"]),
        "name": str(record.get("name") or ""),
        "name_cn": str(record.get("name_cn") or ""),
        "date": date,
        "year": int(date[:4]) if date[:4].isdigit() else None,
        "platform": _int_or_none(record.get("platform")),
        "score": float(record["score"]) if record.get("score") is not None else None,
        "rank": _int_or_none(record.get("rank")),
        # Bangumi users who collected it in any state: a popularity measure,
        # unlike rank, which orders by rating.
        "collects": sum(int(v or 0) for v in (record.get("favorite") or {}).values()),
    }


def person_row(record: dict[str, Any]) -> dict[str, Any]:
    career = record.get("career")
    return {
        "id": int(record["id"]),
        "name": str(record.get("name") or ""),
        "infobox": str(record.get("infobox") or ""),
        "career_json": json.dumps(career, ensure_ascii=False) if career is not None else "",
        "summary": str(record.get("summary") or ""),
    }


def character_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(record["id"]),
        "name": str(record.get("name") or ""),
        "role": _int_or_none(record.get("role")),
        "summary": str(record.get("summary") or ""),
    }


def credit_row(
    subject_id: int,
    person_id: int,
    position_id: int,
    appear_eps: str,
    positions_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    position = positions_by_id.get(position_id)
    if position is None:
        # Position missing from subject_staffs.yml: keep the credit as low-weight evidence.
        cn = en = jp = ""
        normalized_role = f"unknown_position_{position_id}"
        role_tier = "D"
        role_weight = 0.25
    else:
        cn, en, jp = position["cn"], position["en"], position["jp"]
        normalized_role = position["normalized_role"]
        role_tier = position["role_tier"]
        role_weight = position["role_weight"]
    return {
        "subject_id": subject_id,
        "person_id": person_id,
        "position_id": position_id,
        "raw_position": cn,
        "position_cn": cn,
        "position_en": en,
        "position_jp": jp,
        "normalized_role": normalized_role,
        "role_tier": role_tier,
        "role_weight": role_weight,
        "appear_eps": appear_eps,
    }


# --- Writers -----------------------------------------------------------------


def write_positions(driver: Driver, rows: Iterable[dict[str, Any]]) -> int:
    return write_batches(driver, "UNWIND $rows AS row CREATE (p:Position) SET p = row", rows)


def write_anime(driver: Driver, rows: Iterable[dict[str, Any]]) -> int:
    return write_batches(driver, "UNWIND $rows AS row CREATE (a:Anime) SET a = row", rows)


def write_persons(driver: Driver, rows: Iterable[dict[str, Any]]) -> int:
    return write_batches(driver, "UNWIND $rows AS row CREATE (p:Person) SET p = row", rows)


def write_characters(driver: Driver, rows: Iterable[dict[str, Any]]) -> int:
    return write_batches(driver, "UNWIND $rows AS row CREATE (c:Character) SET c = row", rows)


def write_credits(driver: Driver, rows: Iterable[dict[str, Any]]) -> int:
    return write_batches(
        driver,
        """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person_id})
        MATCH (a:Anime {id: row.subject_id})
        CREATE (p)-[r:CREDITED]->(a)
        SET r = row
        REMOVE r.person_id, r.subject_id
        """,
        rows,
    )


def write_cast(driver: Driver, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    written = write_batches(
        driver,
        """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person_id})
        MATCH (c:Character {id: row.character_id})
        CREATE (p)-[:VOICED {
          subject_id: row.subject_id,
          person_character_type: row.person_character_type,
          summary: row.summary
        }]->(c)
        """,
        rows,
    )
    appearances = sorted({(row["character_id"], row["subject_id"]) for row in rows})
    write_batches(
        driver,
        """
        UNWIND $rows AS row
        MATCH (c:Character {id: row.character_id})
        MATCH (a:Anime {id: row.subject_id})
        CREATE (c)-[:APPEARS_IN]->(a)
        """,
        ({"character_id": c, "subject_id": s} for c, s in appearances),
    )
    return written


def _int_or_none(value: Any) -> int | None:
    return int(value) if value is not None else None


def _null_first(item: tuple[int | None, int]) -> tuple[bool, int]:
    key = item[0]
    return (key is not None, key or 0)
