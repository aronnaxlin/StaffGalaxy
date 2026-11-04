"""Read side of the deploy store: one SQLite file exported by `staff_galaxy.export`.

The API never talks to Neo4j. Neo4j stays the build-time knowledge graph; the
export flattens it into tables (see SCHEMA) and stores the galaxy buffers and
meta JSON as blobs, so a deploy is a single file.

Shortest paths need a whole-graph traversal, which SQLite is bad at, so the
store also keeps the Person–Anime incidence matrix in memory as CSR (~1M
entries, data = the person's highest role weight on that anime): one without
NSFW anime (the site's default) and, on first request, one with them.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse


DEFAULT_STORE_PATH = Path("data/deploy/staff_galaxy.sqlite")

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value BLOB);
CREATE TABLE person (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_cn TEXT NOT NULL, name_tw TEXT NOT NULL,
    career_json TEXT NOT NULL, summary TEXT NOT NULL
);
CREATE TABLE anime (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_cn TEXT NOT NULL, date TEXT NOT NULL, year INTEGER,
    nsfw INTEGER NOT NULL
);
CREATE TABLE credit (
    person_id INTEGER NOT NULL, anime_id INTEGER NOT NULL, position_id INTEGER,
    raw_position TEXT, position_cn TEXT, position_en TEXT, normalized_role TEXT,
    role_tier TEXT, role_weight REAL, appear_eps TEXT,
    nsfw INTEGER NOT NULL  -- copy of anime.nsfw, so every credit query filters without a join
);
CREATE TABLE galaxy_node (
    id INTEGER PRIMARY KEY, degree INTEGER NOT NULL, weighted_degree REAL NOT NULL,
    node_size REAL, role_layer TEXT
);
CREATE TABLE collab (
    source INTEGER NOT NULL, target INTEGER NOT NULL, shared INTEGER NOT NULL, score REAL NOT NULL,
    first_year INTEGER, last_year INTEGER, selection_reason TEXT
);
-- Search terms of galaxy members only: search never returns anyone else.
CREATE TABLE search_term (person_id INTEGER NOT NULL, norm TEXT NOT NULL, compact TEXT NOT NULL);
"""

INDEXES = """
CREATE INDEX credit_person ON credit (person_id, anime_id);
CREATE INDEX credit_anime ON credit (anime_id, person_id);
CREATE INDEX collab_source ON collab (source);
CREATE INDEX collab_target ON collab (target);
CREATE INDEX search_term_person ON search_term (person_id);
CREATE INDEX search_term_compact ON search_term (compact);
"""


def store_path() -> Path:
    return Path(os.environ.get("STAFF_GALAXY_STORE", DEFAULT_STORE_PATH))


@dataclass(frozen=True)
class PathGraph:
    """Person–Anime incidence (rows: people, columns: anime) and its bipartite adjacency."""

    person_ids: np.ndarray  # row index -> Bangumi person id (sorted)
    person_anime: sparse.csr_matrix  # P x A, data = max role weight
    anime_person: sparse.csr_matrix  # A x P, same entries transposed
    adjacency: sparse.csr_matrix  # (P + A) square, people first

    def index_of(self, person_id: int) -> int | None:
        i = int(np.searchsorted(self.person_ids, person_id))
        return i if i < len(self.person_ids) and self.person_ids[i] == person_id else None

    def pair_stats(self, a: int, b: int) -> tuple[int, float]:
        """(shared works, collaboration score) for two row indices over the complete graph."""
        pa = self.person_anime
        a_lo, b_lo = pa.indptr[a], pa.indptr[b]
        _, ia, ib = np.intersect1d(
            pa.indices[a_lo : pa.indptr[a + 1]],
            pa.indices[b_lo : pa.indptr[b + 1]],
            assume_unique=True,
            return_indices=True,
        )
        return len(ia), float(np.sqrt(pa.data[a_lo + ia] * pa.data[b_lo + ib]).sum())


class Store:
    def __init__(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(f"Deploy store not found: {path} (run `python -m staff_galaxy.export`)")
        self.path = path
        self._local = threading.local()
        self._path_graphs: dict[bool, PathGraph] = {}
        self._path_graph_lock = threading.Lock()
        meta = dict(self.connection().execute("SELECT key, value FROM meta").fetchall())
        self.snapshot: dict[str, Any] | None = json.loads(meta["snapshot"]) if meta.get("snapshot") else None
        self.graph_info: dict[str, Any] = json.loads(meta["graph"])
        self.graph_buffers: bytes = meta["graph_buffers"]
        self.graph_meta: bytes = meta["graph_meta"]

    def connection(self) -> sqlite3.Connection:
        """One read-only connection per thread (FastAPI runs sync endpoints in a threadpool)."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(f"file:{self.path}?mode=ro&immutable=1", uri=True, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.create_function("sqrt", 1, math.sqrt, deterministic=True)
            self._local.conn = conn
        return conn

    def read(self, query: str, params: Any = ()) -> list[sqlite3.Row]:
        return self.connection().execute(query, params).fetchall()

    def read_one(self, query: str, params: Any = ()) -> sqlite3.Row | None:
        return self.connection().execute(query, params).fetchone()

    def path_graph(self, nsfw: bool = False) -> PathGraph:
        graph = self._path_graphs.get(nsfw)
        if graph is None:
            with self._path_graph_lock:
                graph = self._path_graphs.get(nsfw)
                if graph is None:
                    graph = self._path_graphs[nsfw] = self._build_path_graph(nsfw)
        return graph

    def _build_path_graph(self, nsfw: bool) -> PathGraph:
        rows = np.array(
            self.read(
                "SELECT person_id, anime_id, max(role_weight) FROM credit"
                " WHERE ? OR NOT nsfw GROUP BY person_id, anime_id",
                (nsfw,),
            ),
            dtype=np.float64,
        ).reshape(-1, 3)
        person_ids, person_index = np.unique(rows[:, 0].astype(np.int64), return_inverse=True)
        anime_ids, anime_index = np.unique(rows[:, 1].astype(np.int64), return_inverse=True)
        person_count, anime_count = len(person_ids), len(anime_ids)

        person_anime = sparse.csr_matrix(
            (rows[:, 2], (person_index, anime_index)), shape=(person_count, anime_count)
        )
        person_anime.sort_indices()
        anime_person = person_anime.T.tocsr()
        anime_person.sort_indices()
        adjacency = sparse.csr_matrix(sparse.bmat([[None, person_anime], [anime_person, None]]))
        return PathGraph(person_ids, person_anime, anime_person, adjacency)


_store: Store | None = None
_store_lock = threading.Lock()


def get_store() -> Store:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = Store(store_path())
    return _store


def set_store(store: Store | None) -> None:
    """Swap the process-wide store (tests point the API at a scratch export)."""
    global _store
    _store = store
