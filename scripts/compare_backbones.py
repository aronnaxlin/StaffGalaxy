"""Compare galaxy backbone extraction methods on the live Neo4j graph.

Prints, per method: edges, people covered, largest-component share, modularity
and the share of single-work edges. Read-only; needs Neo4j running and ~2 minutes.

    .venv/bin/python scripts/compare_backbones.py
"""

from __future__ import annotations

import math
from collections import defaultdict

import igraph as ig
import leidenalg
import numpy as np
from scipy.stats import hypergeom, poisson

from staff_galaxy.graph_db import connect_driver, read
from staff_galaxy.visible_edges import benjamini_hochberg, fit_bicm

MIN_ROLE_WEIGHT = 12.0
FDR_Q = 0.05


def load_layer() -> tuple[np.ndarray, np.ndarray]:
    driver = connect_driver()
    try:
        rows = read(
            driver,
            """
            MATCH (p:Person)-[r:CREDITED]->(a:Anime)
            WHERE r.role_weight >= $min_role_weight
            RETURN p.id AS person_id, a.id AS subject_id, max(r.role_weight) AS role_weight
            """,
            min_role_weight=MIN_ROLE_WEIGHT,
        )
    finally:
        driver.close()
    persons = np.array([r["person_id"] for r in rows])
    subjects = np.array([r["subject_id"] for r in rows])
    weights = np.array([r["role_weight"] for r in rows], dtype=float)
    return np.column_stack([persons, subjects]), weights


def main() -> None:
    incidence, weights = load_layer()
    person_ids, person_index = np.unique(incidence[:, 0], return_inverse=True)
    _, subject_index = np.unique(incidence[:, 1], return_inverse=True)
    n = len(person_ids)
    n_subjects = int(subject_index.max()) + 1

    by_subject: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for p, s, w in zip(person_index, subject_index, weights):
        by_subject[int(s)].append((int(p), float(w)))
    pairs: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0, 0.0])
    for people in by_subject.values():
        people.sort()
        for i, (a, wa) in enumerate(people):
            for b, wb in people[i + 1 :]:
                stat = pairs[(a, b)]
                stat[0] += 1
                stat[1] += math.sqrt(wa * wb)
    keys = np.array(list(pairs), dtype=np.int64)
    si, ti = keys[:, 0], keys[:, 1]
    vals = np.array(list(pairs.values()))
    shared, score = vals[:, 0].astype(np.int64), vals[:, 1]
    m = len(keys)

    degree = np.bincount(si, minlength=n) + np.bincount(ti, minlength=n)
    strength = np.bincount(si, score, n) + np.bincount(ti, score, n)
    works = np.bincount(person_index, minlength=n)
    staff = np.bincount(subject_index)
    n_tests = n * (n - 1) // 2

    def ranked(groups: np.ndarray, other: np.ndarray) -> np.ndarray:
        order = np.lexsort((other, -shared, -score, groups))
        g = groups[order]
        start = np.r_[0, np.flatnonzero(np.diff(g)) + 1]
        ranks = np.empty(m, dtype=np.int64)
        ranks[order] = np.arange(m) - np.repeat(start, np.diff(np.r_[start, m])) + 1
        return ranks

    def legacy() -> np.ndarray:
        return (shared >= 2) | (np.minimum(ranked(si, ti), ranked(ti, si)) <= 10)

    def disparity(alpha: float) -> np.ndarray:
        def pval(node: np.ndarray) -> np.ndarray:
            k = degree[node]
            with np.errstate(invalid="ignore"):
                return np.where(k > 1, (1 - score / strength[node]) ** (k - 1), 1.0)

        return (pval(si) < alpha) | (pval(ti) < alpha)

    def hypergeometric_svn() -> np.ndarray:
        log_p = hypergeom.logsf(shared - 1, n_subjects, works[si], works[ti])
        return benjamini_hochberg(log_p, FDR_Q, n_tests)

    def noise_corrected(delta: float) -> np.ndarray:
        ni, nj, total = strength[si], strength[ti], score.sum()
        mean_prior = ni * nj / total / total
        kappa = total / (ni * nj)
        lift = (kappa * score - 1) / (kappa * score + 1)
        var_prior = (ni * nj * (total - ni) * (total - nj)) / (total**4 * (total - 1))
        alpha_prior = mean_prior**2 / var_prior * (1 - mean_prior) - mean_prior
        beta_prior = mean_prior / var_prior * (1 - mean_prior**2) - (1 - mean_prior)
        expected = (alpha_prior + score) / (alpha_prior + beta_prior + total)
        var_n = expected * (1 - expected) * total
        d = 1 / (ni * nj) - total * (ni + nj) / (ni * nj) ** 2
        var_c = var_n * (2 * (kappa + score * d) / (kappa * score + 1) ** 2) ** 2
        return lift - delta * np.sqrt(var_c) > 0

    def bicm() -> np.ndarray:
        person_class, anime_mult, P = fit_bicm(works, staff)
        lam = ((P * anime_mult) @ P.T)[person_class[si], person_class[ti]]
        return benjamini_hochberg(poisson.logsf(shared - 1, lam), FDR_Q, n_tests)

    order = np.lexsort((ti, si, -score))
    full = ig.Graph(n=n, edges=np.column_stack([si[order], ti[order]]).tolist())
    forest = np.zeros(m, dtype=bool)
    forest[order[full.spanning_tree(weights=(-score[order]).tolist(), return_tree=False)]] = True

    print(f"Candidate graph: {m:,} edges, {n:,} people, {n_subjects:,} anime\n")
    print(f"{'method':48} {'edges':>10} {'people':>8} {'LCC':>6} {'Q':>6} {'1-work':>7}")
    for name, keep in [
        ("previous rule (shared>=2 or top 10, 10+10)", legacy()),
        ("disparity filter a=0.05", disparity(0.05)),
        ("hypergeometric SVN FDR 0.05", hypergeometric_svn()),
        ("noise-corrected d=1.64", noise_corrected(1.64)),
        ("BiCM FDR 0.05", bicm()),
        ("BiCM FDR 0.05 + max spanning forest (shipped)", bicm() | forest),
    ]:
        e = np.flatnonzero(keep)
        g = ig.Graph(n=n, edges=np.column_stack([si[e], ti[e]]).tolist())
        w = score[e].tolist()
        part = leidenalg.find_partition(
            g, leidenalg.RBConfigurationVertexPartition, weights=w, seed=42, n_iterations=-1
        )
        people = int((np.bincount(np.r_[si[e], ti[e]], minlength=n) > 0).sum())
        lcc = max(g.connected_components().sizes()) / n
        print(
            f"{name:48} {len(e):>10,} {people:>8,} {lcc:>6.1%} "
            f"{g.modularity(part.membership, weights=w):>6.3f} {(shared[e] == 1).mean():>7.1%}"
        )


if __name__ == "__main__":
    main()
