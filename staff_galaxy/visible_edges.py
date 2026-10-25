"""Statistically validated galaxy backbone.

The person-person collaboration graph is a projection of the bipartite
Person-[:CREDITED]->Anime graph, so a pair co-occurring on works is only
evidence of a real collaboration tie if it co-occurs more than the bipartite
degree structure alone would produce. We test that against the Bipartite
Configuration Model (BiCM; Saracco et al., "Inferring monopartite projections
of bipartite networks: an entropy-based approach", New J. Phys. 19, 2017):

1. Fit BiCM on the layer's incidence matrix. It is the maximum-entropy random
   bipartite graph whose expected degrees equal the observed ones on both
   sides (works per person, staff per anime):
       p_ia = x_i y_a / (1 + x_i y_a).
2. Under BiCM the co-occurrence count V_ij is a sum of independent Bernoullis
   with means p_ia p_ja; its tail P(V_ij >= observed) uses the Poisson
   approximation with lambda_ij = sum_a p_ia p_ja.
3. Benjamini-Hochberg FDR control at q over *every* person pair (pairs that
   never co-occur are tests with p = 1), so the error rate is for the whole
   projection, not just observed pairs.

A single shared work is never significant under this null, so people with few
works would be stranded. The union with the maximum spanning forest of the
candidate graph (by collaboration score) keeps each person attached through
their strongest ties; those edges are labelled `spanning_forest`, never
`bicm_significant`, so topology-preserving edges are not passed off as
statistical evidence.

Complete collaboration evidence stays derivable from CREDITED; COLLAB is a
readability layer only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import igraph as ig
import numpy as np
from neo4j import Driver
from scipy.stats import poisson

from .graph_db import read, run_in_transactions, write_batches


DEFAULT_FDR_Q = 0.05


@dataclass(frozen=True)
class VisibleEdgeStats:
    edge_count: int
    node_count: int
    candidate_edge_count: int
    significant_edges: int
    spanning_forest_edges: int
    people_with_significant_edges: int
    fdr_q: float
    role_layer: str


def fit_bicm(
    row_degrees: np.ndarray,
    col_degrees: np.ndarray,
    *,
    tolerance: float = 1e-12,
    max_iterations: int = 100_000,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Solve BiCM by fixed-point iteration over degree classes.

    Returns (row_class_of, col_class_degrees_multiplicity, P) where P[r, c] is
    the link probability between a row of degree class r and a column of
    degree class c, and row_class_of maps each row to its class.
    """
    row_vals, row_class_of, row_mult = np.unique(row_degrees, return_inverse=True, return_counts=True)
    col_vals, col_mult = np.unique(col_degrees, return_counts=True)
    P = np.full((len(row_vals), len(col_vals)), np.nan)

    # Degenerate classes have exact solutions (p = 0 for degree 0, p = 1 for a
    # node linked to every active node on the other side) at x or y -> 0 / inf,
    # where the fixed point cannot converge. Peel them off, updating the
    # remaining degrees, until only a regular sub-problem is left.
    rows_active = np.ones(len(row_vals), dtype=bool)
    cols_active = np.ones(len(col_vals), dtype=bool)
    row_res = row_vals.astype(float)
    col_res = col_vals.astype(float)
    while True:
        n_cols = col_mult[cols_active].sum()
        n_rows = row_mult[rows_active].sum()
        empty_rows = rows_active & (row_res <= 0)
        full_rows = rows_active & (row_res >= n_cols)
        empty_cols = cols_active & (col_res <= 0)
        full_cols = cols_active & (col_res >= n_rows)
        if not ((empty_rows | full_rows).any() or (empty_cols | full_cols).any()):
            break
        P[np.ix_(empty_rows, cols_active)] = 0.0
        P[np.ix_(rows_active, empty_cols)] = 0.0
        P[np.ix_(full_rows, cols_active & ~empty_cols)] = 1.0
        P[np.ix_(rows_active & ~empty_rows, full_cols)] = 1.0
        col_res[cols_active] -= row_mult[full_rows].sum()
        row_res[rows_active] -= col_mult[full_cols].sum()
        rows_active &= ~(empty_rows | full_rows)
        cols_active &= ~(empty_cols | full_cols)

    if rows_active.any() and cols_active.any():
        r_vals, r_mult = row_res[rows_active], row_mult[rows_active]
        c_vals, c_mult = col_res[cols_active], col_mult[cols_active]
        x = r_vals / math.sqrt((r_vals * r_mult).sum())
        y = c_vals / math.sqrt((c_vals * c_mult).sum())
        for _ in range(max_iterations):
            x_new = r_vals / ((y / (1 + np.outer(x, y))) * c_mult).sum(axis=1)
            y_new = c_vals / ((x_new[:, None] / (1 + np.outer(x_new, y))) * r_mult[:, None]).sum(axis=0)
            change = max(np.abs(x_new - x).max() / x_new.max(), np.abs(y_new - y).max() / y_new.max())
            x, y = x_new, y_new
            if change < tolerance:
                break
        else:
            raise RuntimeError("BiCM fit did not converge")
        xy = np.outer(x, y)
        P[np.ix_(rows_active, cols_active)] = xy / (1 + xy)
    return row_class_of, col_mult, P


def benjamini_hochberg(log_p: np.ndarray, q: float, n_tests: int) -> np.ndarray:
    """BH rejections among the given tests when n_tests hypotheses were tested in total."""
    order = np.argsort(log_p, kind="stable")
    thresholds = np.log(q * np.arange(1, len(log_p) + 1) / n_tests)
    passed = np.flatnonzero(log_p[order] <= thresholds)
    keep = np.zeros(len(log_p), dtype=bool)
    if len(passed):
        keep[order[: passed.max() + 1]] = True
    return keep


def build_visible_person_edges(
    driver: Driver,
    *,
    min_role_weight: float = 12.0,
    fdr_q: float = DEFAULT_FDR_Q,
) -> VisibleEdgeStats:
    """Materialize the galaxy backbone as (:Person)-[:COLLAB]->(:Person)."""
    rows = read(
        driver,
        """
        MATCH (p:Person)-[r:CREDITED]->(a:Anime)
        WHERE r.role_weight >= $min_role_weight
        RETURN a.id AS subject_id, a.year AS year, p.id AS person_id,
               max(r.role_weight) AS role_weight
        ORDER BY subject_id, person_id
        """,
        min_role_weight=min_role_weight,
    )
    subjects = np.fromiter((r["subject_id"] for r in rows), dtype=np.int64, count=len(rows))
    persons = np.fromiter((r["person_id"] for r in rows), dtype=np.int64, count=len(rows))
    weights = np.fromiter((r["role_weight"] for r in rows), dtype=np.float64, count=len(rows))
    years = np.fromiter((r["year"] if r["year"] is not None else -1 for r in rows), dtype=np.int64, count=len(rows))

    person_ids, person_index = np.unique(persons, return_inverse=True)
    _, subject_index = np.unique(subjects, return_inverse=True)
    n_people = len(person_ids)

    # --- Candidate pairs: every co-occurrence in the layer -------------------
    pair_shared: dict[tuple[int, int], int] = {}
    pair_score: dict[tuple[int, int], float] = {}
    pair_first: dict[tuple[int, int], int] = {}
    pair_last: dict[tuple[int, int], int] = {}
    starts = np.r_[0, np.flatnonzero(np.diff(subjects)) + 1, len(subjects)]
    for begin, end in zip(starts[:-1], starts[1:]):
        members = person_index[begin:end]
        member_weights = weights[begin:end]
        year = int(years[begin])
        for i in range(len(members)):
            a, wa = int(members[i]), member_weights[i]
            for j in range(i + 1, len(members)):
                key = (a, int(members[j]))
                pair_shared[key] = pair_shared.get(key, 0) + 1
                pair_score[key] = pair_score.get(key, 0.0) + math.sqrt(wa * member_weights[j])
                if year >= 0:
                    pair_first[key] = min(pair_first.get(key, year), year)
                    pair_last[key] = max(pair_last.get(key, year), year)

    keys = np.array(list(pair_shared), dtype=np.int64).reshape(-1, 2)
    src, dst = keys[:, 0], keys[:, 1]
    shared = np.fromiter(pair_shared.values(), dtype=np.int64, count=len(keys))
    score = np.fromiter((pair_score[k] for k in pair_shared), dtype=np.float64, count=len(keys))

    # --- BiCM significance ----------------------------------------------------
    works_per_person = np.bincount(person_index, minlength=n_people)
    staff_per_anime = np.bincount(subject_index)
    person_class, anime_class_mult, P = fit_bicm(works_per_person, staff_per_anime)
    expected = ((P * anime_class_mult) @ P.T)[person_class[src], person_class[dst]]
    log_p = poisson.logsf(shared - 1, expected)
    significant = benjamini_hochberg(log_p, fdr_q, n_people * (n_people - 1) // 2)

    # --- Maximum spanning forest by collaboration score -----------------------
    order = np.lexsort((dst, src, -score))  # deterministic tie-breaking
    graph = ig.Graph(n=n_people, edges=np.column_stack([src[order], dst[order]]).tolist())
    forest = np.zeros(len(keys), dtype=bool)
    forest[order[graph.spanning_tree(weights=(-score[order]).tolist(), return_tree=False)]] = True

    keep = np.flatnonzero(significant | forest)
    role_layer = f"Weight >={min_role_weight}"
    edge_rows: list[dict[str, object]] = []
    for e in keep:
        key = (int(src[e]), int(dst[e]))
        edge_rows.append(
            {
                "source": int(person_ids[key[0]]),
                "target": int(person_ids[key[1]]),
                "shared_works_count": int(shared[e]),
                "collaboration_score": float(score[e]),
                "first_year": pair_first.get(key),
                "last_year": pair_last.get(key),
                "role_layer": role_layer,
                "expected_shared_works": float(expected[e]),
                # -log10 p under BiCM, capped so an underflowing tail stays a finite float.
                "significance": float(min(-log_p[e] / math.log(10), 1e300)),
                "selection_reason": "bicm_significant" if significant[e] else "spanning_forest",
            }
        )

    clear_visible_person_edges(driver)
    write_batches(
        driver,
        """
        UNWIND $rows AS row
        MATCH (s:Person {id: row.source})
        MATCH (t:Person {id: row.target})
        CREATE (s)-[e:COLLAB]->(t)
        SET e = row
        REMOVE e.source, e.target
        """,
        edge_rows,
    )

    endpoints = np.r_[src[keep], dst[keep]]
    significant_endpoints = np.r_[src[significant], dst[significant]]
    return VisibleEdgeStats(
        edge_count=len(keep),
        node_count=len(np.unique(endpoints)),
        candidate_edge_count=len(keys),
        significant_edges=int(significant.sum()),
        spanning_forest_edges=int((forest & ~significant).sum()),
        people_with_significant_edges=len(np.unique(significant_endpoints)),
        fdr_q=fdr_q,
        role_layer=role_layer,
    )


def clear_visible_person_edges(driver: Driver) -> None:
    run_in_transactions(
        driver,
        "MATCH ()-[e:COLLAB]->() CALL (e) { DELETE e } IN TRANSACTIONS OF 50000 ROWS",
    )
