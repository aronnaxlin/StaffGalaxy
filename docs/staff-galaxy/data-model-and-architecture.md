# Data Model And Architecture

## Architecture Summary

Staff Galaxy uses a live API architecture over a Neo4j knowledge graph, not static JSON export:

```text
Bangumi Archive zip
  → Python ingest pipeline (streams jsonlines from the zip)
  → Neo4j 5 knowledge graph
  → FastAPI backend (staff_galaxy/api.py, Cypher)
  → React + Cosmos.gl frontend
```

The frontend queries the API directly. There is no intermediate static file export layer.

> The DuckDB table model this document used to describe (`subjects`, `credits`,
> `person_collaboration_edges`, `visible_person_edges`, `graph_nodes`, …) was
> replaced by the graph below on the `neo4j-migration` branch.

## Knowledge Graph Model

The authoritative schema is the module docstring of `staff_galaxy/graph_db.py`;
`AGENTS.md` "Graph Schema" summarizes it.

```text
(:Person)-[:CREDITED {position_id, position_cn, normalized_role, role_tier, role_weight, appear_eps}]->(:Anime)
(:Person)-[:VOICED {subject_id}]->(:Character)-[:APPEARS_IN]->(:Anime)
(:Person)-[:HAS_SEARCH_TERM]->(:SearchTerm {norm, compact, kind})
(:Position {position_id, cn, en, jp, normalized_role, role_tier, role_weight})
(:DataSnapshot {snapshot_id: 'current', archive_name, archive_created_at, ...})
```

Only `subject.type = 2` (anime) subjects and `person.type = 1` (real individuals)
are loaded. Credits are de-duplicated on (subject, person, position, appear_eps);
positions missing from `subject_staffs.yml` get `unknown_position_<id>`, tier D,
weight 0.25.

## Visible Graph Model

The galaxy is a derived layer written back into the same graph:

```text
(:Person:GalaxyNode {x, y, community_id, visible_degree, visible_weighted_degree, node_size, layout_method})
(:Person)-[:COLLAB {shared_works_count, collaboration_score, first_year, last_year,
                    top_neighbor_rank, selection_reason}]->(:Person)   // source id < target id
```

The complete collaboration graph (~34M person pairs on the 2026-10 dump) is not
materialized. Any pair's evidence and all shortest paths are derived from
`CREDITED` at query time.

## Role Tier System

Six tiers with exponential weights:

| Tier | Weight | Count | Description |
|---|---|---|---|
| S | 50.0 | 2 | Director, Chief Director |
| A | 25.0 | 7 | Original Creator, Series Composition, Character Design, etc. |
| B | 12.0 | 15 | Script, Music, Storyboard, Episode Director, Producer, etc. |
| C | 6.0 | 40 | Department heads: Art Director, Photography Director, Sound Director, etc. |
| D | 3.0 | 76 | Skilled production: Key Animation, Background Art, Photography, etc. |
| E | 1.0 | 15 | Support: In-Between Animation, Digital Paint, Production Assistant |
| F | 0.3 | 6 | Minimal: Special Thanks, Assistance, Production Company |

## Collaboration Scoring

Per shared work:

```text
contribution = SQRT(role_weight_a × role_weight_b)
```

Total:

```text
collaboration_score = SUM(contribution) across all shared works
```

The geometric mean ensures both roles must be significant for a high score:
- Two directors on 1 show = 50 points
- Two key animators on ~17 shows ≈ 50 points
- Director + in-betweener on 1 show ≈ 7 points

## Graph Backbone Selection

Galaxy members are everyone with at least one credit at `role_weight >= 12.0`
(S+A+B tiers). Candidate edges are all co-occurrences inside that layer
(1,646,587 pairs on `dump-2026-10-20`). The backbone keeps an edge if:

1. **It is statistically validated.** The person–anime layer is fitted with the
   Bipartite Configuration Model (BiCM; Saracco et al., *New J. Phys.* 19,
   2017), the maximum-entropy random bipartite graph that reproduces every
   person's work count and every anime's staff count. A pair's co-occurrence
   count is tested against it (Poisson approximation of the Poisson-binomial
   tail), with Benjamini–Hochberg FDR control at q = 0.05 over **all** person
   pairs. → `selection_reason = 'bicm_significant'`, or
2. **It is in the maximum spanning forest** of the candidate graph (by
   collaboration score), so people with too few works for significance still
   attach through their strongest tie. → `selection_reason = 'spanning_forest'`.

Each `COLLAB` edge stores `expected_shared_works` (BiCM expectation) and
`significance` (−log10 p). Result on `dump-2026-10-20`: 107,489 edges, of which
95,050 significant (covering 13,561 people) and 12,439 spanning-forest.

Why BiCM: the graph is a projection of a bipartite graph, where co-occurrence is
driven by degree heterogeneity on **both** sides (a person with 300 works vs. 1;
a 700-staff production vs. a 5-person short). Given only the two degree
sequences, BiCM is the maximum-entropy (least-biased) null model. Measured on
`dump-2026-10-20` with `scripts/compare_backbones.py`:

| Method | Edges kept | People covered | Modularity | Single-work edges | Note |
|---|---:|---:|---:|---:|---|
| Previous rule (shared ≥ 2 or top 10, ranked as 10 + 10) | 589,011 | 22,840 | 0.463 | 29.2% | Heuristic thresholds, no null model |
| Disparity filter, α = 0.05 (Serrano et al. 2009) | 56,985 | 9,801 | 0.626 | 0.1% | Every co-worker on a work gets the same weight, so few edges stand out |
| Hypergeometric SVN, FDR 0.05 (Tumminello et al. 2011) | 160,990 | 14,441 | 0.645 | 0.0% | Null constrains person degrees only; ignores anime size |
| Noise-corrected, δ = 1.64 (Coscia & Neffke 2017) | 1,425,742 | 22,840 | 0.417 | 73.7% | Per-edge threshold, no multiple-testing correction |
| BiCM, FDR 0.05 | 95,050 | 13,561 | 0.751 | 0.0% | Constrains both degree sequences |
| **BiCM, FDR 0.05 + max spanning forest (shipped)** | **107,489** | **22,840** | **0.755** | 8.5% | Forest edges labelled `spanning_forest` |

All FDR methods count every person pair as a hypothesis (~270M), not only
observed pairs. Reproduce with:

```bash
.venv/bin/python scripts/compare_backbones.py
```

## API Architecture

### Endpoint Design

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/graph/buffers` | GET | Binary galaxy geometry (positions, sizes, community, edges) |
| `/api/graph/meta` | GET | Galaxy node metadata (names, degrees) |
| `/api/person/{id}/galaxy` | GET | Person-centered galaxy with data-driven layout |
| `/api/person/{id}/detail` | GET | Person summary stats, top roles, and recent works |
| `/api/person/{id}/credits` | GET | Complete row-level anime credit history with raw roles |
| `/api/collaboration/{a}/{b}` | GET | Shared works with per-person roles |
| `/api/path/{a}/{b}` | GET | Cypher `ALL SHORTEST` paths between two people |
| `/api/search/persons` | GET | Search with aliases, CJK variants, romanization, and bounded fuzzy fallback |
| `/api/manifest` | GET | Graph URI, snapshot metadata, galaxy counts |

Endpoint data is intentionally layered:

- Galaxy endpoints use `:GalaxyNode` and `COLLAB`.
- Person detail and credit endpoints use complete `CREDITED` facts.
- Collaboration and path endpoints traverse complete `CREDITED` relationships
  through `:Anime` nodes.
- Manifest and evidence-bearing endpoints include the current Archive snapshot.

### Search Design

Single-input unified search that auto-detects:
- **Numeric ID**: Exact match + ILIKE fallback
- **Text query**: Multi-term AND matching with CJK variant expansion per term
- **CJK variants**: ~150 simplified→Japanese kanji pairs, Cartesian product capped at 12 variants
- **Archive aliases**: Selected `infobox` fields and aliases are normalized into `:SearchTerm` nodes
- **Fuzzy fallback**: If exact/prefix/contains search leaves room, bounded typo matching runs against compact indexed terms. Same-prefix, similar-length candidates are fetched with Cypher and scored in Python with a bounded optimal-string-alignment edit distance (adjacent transpositions cost 1), for both romanized and CJK/kana input.

### Display Names

Person payloads include original `name` and optional Archive-provided `nameCn`. The frontend stores `staffGalaxy.personNameMode` in localStorage and supports:

- `original`: show Archive original/Japanese name.
- `cn`: show `nameCn` when present; otherwise fall back to `name`.

When simplified Chinese is primary and the original differs, panels and search pills show the original as secondary context.

### Path Finding

Cypher `ALL SHORTEST (a)-[:CREDITED]-{1,2·maxDepth}(b)` enumerates shortest
paths over the bipartite Person–Anime graph (one collaboration hop is two
relationships). Paths that differ only in the linking anime collapse to one
person sequence; sequences are ranked by weakest step, then total score. Each
path includes node IDs and per-step sharedWorksCount / collaborationScore.
Frontend renders as depth-layered SVG constellation.

Paths traverse complete `CREDITED`, not `COLLAB`. This preserves hidden
low-tier relationships for path and compare workflows.

### Direct Comparison

`/compare?from={id}&to={id}` is a frontend route for the same Constellation
surface in comparison mode. It first loads both person search entries, then:

1. Calls `/api/path/{a}/{b}` to establish whether a connection exists.
2. If the shortest path degree is `1`, calls `/api/collaboration/{a}/{b}` and
   renders direct shared-work evidence before the path legend.
3. If the shortest path degree is greater than `1`, shows a no-direct-evidence
   notice and renders shortest paths.

Person-panel collaborator rows can open this route directly.

## Detail Views

The SQL views of the DuckDB era are gone; each detail endpoint aggregates
`CREDITED` directly in Cypher (per-person tier breakdowns, role counts, recent
works, raw credit rows).

## Frontend Data Flow

```text
App.tsx (mount)
  → loadGlobalGraph()    →  GET /api/graph/buffers + /api/graph/meta
  → buildGlobalPayload() →  typed arrays
  → CosmosGalaxyView     →  WebGL render

User clicks node (or search / /person/{id})
  → URL /person/{id}; the galaxy stays loaded and focuses the person in place
  → loadPersonGalaxy(id)        → GET /api/person/{id}/galaxy (sidebar collaborator list)
  → loadPersonKnowledgeGraph(id) → GET /api/person/{id}/knowledge-graph
  → PersonSidebar        →  知识图谱 tab (react-force-graph + SPO triples), 合作者, 履历

User expands collaboration
  → loadCollaborationDetail(a, b) → GET /api/collaboration/{a}/{b}
  → shows shared works, roles, years

User expands complete credits
  → loadPersonCredits(id) → GET /api/person/{id}/credits?limit=2000
  → groups raw credit rows by anime work

User opens path route
  → /path?from={a}&to={b}
  → ConstellationView    →  two locked SearchBars
  → loadShortestPath(a,b) → GET /api/path/{a}/{b}
  → SVG rendering        →  Bezier curves connecting depth-layered nodes

User opens compare route
  → /compare?from={a}&to={b}
  → loadShortestPath(a,b)
  → degree 1: loadCollaborationDetail(a,b)
  → degree 2+: show no-direct evidence notice and shortest paths
```

### Runtime Metrics

The frontend records lightweight runtime measurements in
`window.__staffGalaxyMetrics` and emits `staff-galaxy:metric` events.

Current metric types:

- `api-response`: URL, status, success flag, and request duration.
- `cosmos-ready`: graph level, node count, total edges, visible edges, and edge cutoff.

These metrics are used by `reports/graph-performance.md` to record production
preview behavior for global graph, person graph, compare, path, and detail
interactions.

## Local Rebuild And Migration Workflow

Full rebuild:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m staff_galaxy.cli
```

The full rebuild (requires `docker compose up -d neo4j` and `.env` credentials):

1. Wipes the Neo4j graph and creates constraints and indexes.
2. Streams the Archive zip and writes `Position`, `Anime`, `Person`, `CREDITED`,
   `Character`, `VOICED`, and `APPEARS_IN`.
3. Rebuilds the derived layer: sparse `COLLAB` edges, `GalaxyNode` membership
   and sizes, the hierarchical Leiden layout, and `SearchTerm` nodes.
4. Records the current `DataSnapshot` node.
5. Writes `reports/data-audit.md`.

Rebuild only the derived layer (after role weight or layout changes):

```bash
.venv/bin/python -m staff_galaxy.cli --derived-only
```

## Local Runtime Workflow

Development:

```bash
.venv/bin/uvicorn staff_galaxy.api:app --reload --host 127.0.0.1 --port 8000
cd frontend && npm run dev -- --host 127.0.0.1
```

Production preview for measurements:

```bash
cd frontend
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

Vite dev and preview both proxy `/api` to `http://127.0.0.1:8000`.
