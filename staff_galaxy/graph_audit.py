from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass

import duckdb


LAYER_TIERS: dict[str, set[str]] = {
    "Tier A": {"A"},
    "Tier A+B": {"A", "B"},
    "Tier A+B+C": {"A", "B", "C"},
    "Tier A+B+C+D": {"A", "B", "C", "D"},
}


@dataclass(frozen=True)
class TopKStats:
    k: int
    edge_count: int
    node_count: int


@dataclass(frozen=True)
class LayerAudit:
    name: str
    subjects: int
    persons: int
    credits: int
    estimated_pair_contributions: int
    max_people_on_one_subject: int
    max_people_subject_id: int | None
    max_people_subject_name: str
    materialized: bool
    unique_edges: int | None
    nodes_with_edges: int | None
    shared_works_ge_2_edges: int | None
    degree_median: float | None
    degree_p95: int | None
    degree_max: int | None
    top_k: tuple[TopKStats, ...]


def audit_graph_layers(
    conn: duckdb.DuckDBPyConnection,
    materialize_pair_limit: int,
    top_k_values: tuple[int, ...] = (5, 10, 20),
) -> list[LayerAudit]:
    rows = conn.execute(
        """
        SELECT c.subject_id, c.person_id, c.role_tier, c.role_weight, s.name, s.name_cn
        FROM credits c
        JOIN subjects s ON s.id = c.subject_id
        WHERE c.role_tier IS NOT NULL
        """
    ).fetchall()

    layer_subject_people: dict[str, dict[int, dict[int, float]]] = {
        layer: defaultdict(dict) for layer in LAYER_TIERS
    }
    subject_names: dict[int, str] = {}
    layer_credit_counts = Counter[str]()

    for subject_id, person_id, role_tier, role_weight, name, name_cn in rows:
        label = name_cn or name or ""
        subject_names[int(subject_id)] = str(label)
        for layer, tiers in LAYER_TIERS.items():
            if role_tier in tiers:
                people = layer_subject_people[layer][int(subject_id)]
                people[int(person_id)] = max(people.get(int(person_id), 0.0), float(role_weight))
                layer_credit_counts[layer] += 1

    audits: list[LayerAudit] = []
    for layer_name, subject_people in layer_subject_people.items():
        audits.append(
            _audit_layer(
                layer_name,
                subject_people,
                dict(subject_names),
                layer_credit_counts[layer_name],
                materialize_pair_limit,
                top_k_values,
            )
        )
    return audits


def _audit_layer(
    name: str,
    subject_people: dict[int, dict[int, float]],
    subject_names: dict[int, str],
    credit_count: int,
    materialize_pair_limit: int,
    top_k_values: tuple[int, ...],
) -> LayerAudit:
    persons: set[int] = set()
    estimated_pair_contributions = 0
    max_people_on_one_subject = 0
    max_people_subject_id: int | None = None
    subjects = 0

    for subject_id, people in subject_people.items():
        n = len(people)
        if n == 0:
            continue
        subjects += 1
        persons.update(people)
        estimated_pair_contributions += n * (n - 1) // 2
        if n > max_people_on_one_subject:
            max_people_on_one_subject = n
            max_people_subject_id = subject_id

    if estimated_pair_contributions > materialize_pair_limit:
        return LayerAudit(
            name=name,
            subjects=subjects,
            persons=len(persons),
            credits=credit_count,
            estimated_pair_contributions=estimated_pair_contributions,
            max_people_on_one_subject=max_people_on_one_subject,
            max_people_subject_id=max_people_subject_id,
            max_people_subject_name=subject_names.get(max_people_subject_id or -1, ""),
            materialized=False,
            unique_edges=None,
            nodes_with_edges=None,
            shared_works_ge_2_edges=None,
            degree_median=None,
            degree_p95=None,
            degree_max=None,
            top_k=(),
        )

    edges: dict[tuple[int, int], list[float]] = {}
    for people in subject_people.values():
        items = list(people.items())
        for i, (source, source_weight) in enumerate(items):
            for target, target_weight in items[i + 1 :]:
                a, b = sorted((source, target))
                stat = edges.setdefault((a, b), [0.0, 0.0])
                stat[0] += 1
                stat[1] += math.sqrt(source_weight * target_weight)

    degree = Counter[int]()
    shared_works_ge_2_edges = 0
    adjacency: dict[int, list[tuple[float, float, int, tuple[int, int]]]] = defaultdict(list)
    for edge, (shared_works, score) in edges.items():
        source, target = edge
        degree[source] += 1
        degree[target] += 1
        if shared_works >= 2:
            shared_works_ge_2_edges += 1
        adjacency[source].append((score, shared_works, target, edge))
        adjacency[target].append((score, shared_works, source, edge))

    degree_values = sorted(degree.values())
    if degree_values:
        degree_median = float(statistics.median(degree_values))
        degree_p95 = degree_values[int((len(degree_values) - 1) * 0.95)]
        degree_max = max(degree_values)
    else:
        degree_median = 0.0
        degree_p95 = 0
        degree_max = 0

    top_k_stats: list[TopKStats] = []
    for k in top_k_values:
        selected_edges: set[tuple[int, int]] = set()
        selected_nodes: set[int] = set()
        for person_id, neighbors in adjacency.items():
            neighbors.sort(reverse=True)
            for _, _, _, edge in neighbors[:k]:
                selected_edges.add(edge)
                selected_nodes.update(edge)
            if neighbors:
                selected_nodes.add(person_id)
        top_k_stats.append(TopKStats(k, len(selected_edges), len(selected_nodes)))

    return LayerAudit(
        name=name,
        subjects=subjects,
        persons=len(persons),
        credits=credit_count,
        estimated_pair_contributions=estimated_pair_contributions,
        max_people_on_one_subject=max_people_on_one_subject,
        max_people_subject_id=max_people_subject_id,
        max_people_subject_name=subject_names.get(max_people_subject_id or -1, ""),
        materialized=True,
        unique_edges=len(edges),
        nodes_with_edges=len(degree),
        shared_works_ge_2_edges=shared_works_ge_2_edges,
        degree_median=degree_median,
        degree_p95=degree_p95,
        degree_max=degree_max,
        top_k=tuple(top_k_stats),
    )
