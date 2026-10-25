from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from neo4j import Driver

from .graph_db import read, run_in_transactions, write_batches


_BRACKET_TERM_RE = re.compile(r"\[([^\[\]\r\n]+)\]")
_FIELD_RE = re.compile(r"^\|([^=]+)=[ \t]*(.*)$", re.MULTILINE)
_ALIAS_SPLIT_RE = re.compile(r"[、,，;；/／]+")
_COMPACT_DROP_RE = re.compile(r"[\s\-_・·.．,，、/／()（）\[\]【】]+")

_SEARCH_FIELDS = {
    "简体中文名",
    "繁体中文名",
    "繁體中文名",
    "第二中文名",
    "英文名",
    "日文名",
    "纯假名",
    "罗马字",
    "昵称",
}


@dataclass(frozen=True)
class SearchIndexStats:
    person_count: int
    term_count: int


def normalize_search_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", text).strip()


def compact_search_text(value: str) -> str:
    return _COMPACT_DROP_RE.sub("", normalize_search_text(value))


def _clean_term(value: str) -> str:
    value = value.strip()
    value = value.strip("{}")
    value = value.strip()
    return value


def _split_alias_value(value: str) -> list[str]:
    value = _clean_term(value)
    if not value:
        return []
    parts = [_clean_term(part) for part in _ALIAS_SPLIT_RE.split(value)]
    return [part for part in parts if part]


def extract_infobox_search_terms(infobox: str) -> list[str]:
    terms: list[str] = []

    for key, value in _FIELD_RE.findall(infobox or ""):
        key = key.strip()
        if key in _SEARCH_FIELDS:
            terms.extend(_split_alias_value(value))

    for item in _BRACKET_TERM_RE.findall(infobox or ""):
        if "|" in item:
            key, value = item.split("|", 1)
            if key.strip() in _SEARCH_FIELDS:
                terms.extend(_split_alias_value(value))
            continue
        terms.extend(_split_alias_value(item))

    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        norm = normalize_search_text(term)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique.append(term)
    return unique


def _extract_person_field(infobox: str, field_names: set[str]) -> str:
    for key, value in _FIELD_RE.findall(infobox or ""):
        if key.strip() in field_names:
            terms = _split_alias_value(value)
            return terms[0] if terms else ""

    for item in _BRACKET_TERM_RE.findall(infobox or ""):
        if "|" not in item:
            continue
        key, value = item.split("|", 1)
        if key.strip() in field_names:
            terms = _split_alias_value(value)
            return terms[0] if terms else ""
    return ""


def extract_person_name_cn(infobox: str) -> str:
    """Return the Archive-provided simplified Chinese person name, if present."""
    return _extract_person_field(infobox, {"简体中文名"})


def extract_person_name_tw(infobox: str) -> str:
    """Return the Archive-provided traditional Chinese person name, if present."""
    return _extract_person_field(infobox, {"繁体中文名", "繁體中文名"})


def build_person_search_terms(driver: Driver) -> SearchIndexStats:
    run_in_transactions(
        driver,
        "MATCH (t:SearchTerm) CALL (t) { DETACH DELETE t } IN TRANSACTIONS OF 10000 ROWS",
    )
    rows = read(driver, "MATCH (p:Person) RETURN p.id AS id, p.name AS name, p.infobox AS infobox")

    records: list[dict[str, object]] = []
    for row in rows:
        person_id, name, infobox = row["id"], row["name"], row["infobox"] or ""
        person_terms: list[tuple[str, str]] = [(name, "name")] if name else []
        person_terms.extend((term, "infobox") for term in extract_infobox_search_terms(infobox))

        seen: set[str] = set()
        for term, kind in person_terms:
            norm = normalize_search_text(term)
            compact = compact_search_text(term)
            key = compact or norm
            if not key or key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "person_id": int(person_id),
                    "term": term,
                    "norm": norm,
                    "compact": compact,
                    "kind": kind,
                }
            )

    write_batches(
        driver,
        """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person_id})
        CREATE (p)-[:HAS_SEARCH_TERM]->(t:SearchTerm)
        SET t = row
        """,
        records,
    )
    return SearchIndexStats(person_count=len(rows), term_count=len(records))
