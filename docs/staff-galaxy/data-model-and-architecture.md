# Data Model And Architecture

## Architecture Summary

Staff Galaxy uses a live API architecture, not static JSON export:

```text
Bangumi Archive files
  → Python ingest pipeline
  → DuckDB database
  → FastAPI backend (staff_galaxy/api.py)
  → React + Cosmos.gl frontend
```

The frontend queries the API directly. There is no intermediate static file export layer.

## Raw Fact Model

### subjects

```sql
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
);
```

Only `type = 2` (anime) is used for STAFF graph analysis.

### persons

```sql
CREATE TABLE persons (
  id INTEGER PRIMARY KEY,
  name TEXT,           -- Japanese kanji (no name_cn column)
  type INTEGER,        -- 1=individual, 2=company, 3=group
  infobox TEXT,        -- raw Archive infobox for aliases/romanization
  career_json TEXT,
  summary TEXT
);
```

Only `type = 1` (real individuals) are default graph nodes. **No `name_cn` column exists**. Search and display-name variants use the raw Archive `infobox` plus CJK variant mapping to bridge simplified Chinese, aliases, kana, and romanized names without inventing translations. API responses expose `name` and, when present, `nameCn` extracted from the Archive `简体中文名` field.

### credits

```sql
CREATE TABLE credits (
  subject_id INTEGER,
  person_id INTEGER,
  position_id INTEGER,
  raw_position TEXT,
  position_cn TEXT,
  position_en TEXT,
  position_jp TEXT,
  normalized_role TEXT,
  role_tier TEXT,       -- S, A, B, C, D, E, or F
  role_weight DOUBLE,   -- 50.0 to 0.3, exponential scale
  appear_eps TEXT
);
```

`credits` is the central fact table. All person-person edges are derived from it. Positions are mapped from Bangumi numeric IDs via `staff_positions`.

### data_snapshots

```sql
CREATE TABLE data_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  archive_name TEXT,
  archive_created_at TEXT,
  archive_size_bytes BIGINT,
  built_at TIMESTAMP,
  source_url TEXT
);
```

The full rebuild records the current Bangumi Archive zip as `snapshot_id = 'current'`. Existing local databases can be backfilled with `scripts/migrate_data_snapshot.py`. The API exposes this metadata through `/api/manifest`, person detail/credits responses, and collaboration evidence responses so graph facts can be tied back to a concrete Archive snapshot.

### person_search_terms

```sql
CREATE TABLE person_search_terms (
  person_id INTEGER,
  term TEXT,
  term_norm TEXT,
  term_compact TEXT,
  term_kind TEXT
);
```

`person_search_terms` is rebuilt from `persons.name` and selected real Archive infobox fields such as `简体中文名`, `英文名`, `日文名`, `纯假名`, `罗马字`, and aliases. The API searches normalized and compact forms with multi-term AND matching.

### staff_positions

```sql
CREATE TABLE staff_positions (
  position_id INTEGER PRIMARY KEY,
  cn TEXT,
  en TEXT,
  jp TEXT,
  normalized_role TEXT,
  role_tier TEXT,
  role_weight DOUBLE
);
```

163 position definitions. Tier and weight assignments live in `staff_galaxy/roles.py`.

## Visible Graph Model

### person_collaboration_edges

```sql
CREATE TABLE person_collaboration_edges (
  source_person_id INTEGER,
  target_person_id INTEGER,
  shared_works_count INTEGER,
  collaboration_score DOUBLE,
  first_year INTEGER,
  last_year INTEGER,
  selection_reason TEXT
);
```

This is the complete staff collaboration graph derived from all anime staff
credits, not the renderer backbone. It includes lower-tier staff collaborations
that may be hidden from the default galaxy. Direct comparison and shortest-path
queries use this table so hidden real relationships remain queryable.

Current snapshot:

- 26,017,438 complete staff edges.
- 41,472,689 shared-work evidence pairs.
- `selection_reason = 'all_staff'`.

### visible_person_edges

```sql
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
);
```

Built from credits where `role_weight >= 12.0` (S+A+B tiers). Filters:

```text
sharedWorksCount >= 2 OR top 10 strongest neighbors per endpoint
```

Current snapshot: ~518,581 edges across ~21,006 people.

`visible_person_edges` is a readability and performance layer. It is not the
truth source for collaboration existence.

### graph_nodes

```sql
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
);
```

Coordinates use `deterministic_spiral_v1` layout. Node size is log-scaled against `visible_weighted_degree`.

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

The graph backbone includes anyone with at least one credit at `role_weight >= 12.0` (S+A+B tiers). Edges are included if:

1. `sharedWorksCount >= 2`, OR
2. The edge is among the top 10 strongest per endpoint

This replaced the old "Tier A only" approach, broadening the graph while maintaining readable density.

## API Architecture

### Endpoint Design

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/graph/{level}/nodes` | GET | Galaxy nodes (global, l0, l1) |
| `/api/graph/{level}/edges` | GET | Galaxy edges with sharedWorksCount, collaborationScore |
| `/api/person/{id}/galaxy` | GET | Person-centered galaxy with data-driven layout |
| `/api/person/{id}/detail` | GET | Person summary stats, top roles, and recent works |
| `/api/person/{id}/credits` | GET | Complete row-level anime credit history with raw roles |
| `/api/collaboration/{a}/{b}` | GET | Shared works with per-person roles |
| `/api/path/{a}/{b}` | GET | BFS shortest paths between two people |
| `/api/search/persons` | GET | Search with aliases, CJK variants, romanization, and bounded fuzzy fallback |
| `/api/manifest` | GET | DB path, snapshot metadata, level counts |

Endpoint data is intentionally layered:

- Galaxy endpoints use `visible_person_edges` and `graph_nodes`.
- Person detail and credit endpoints use complete `credits` facts.
- Collaboration and path endpoints use `person_collaboration_edges` plus
  evidence joins back to `credits` and `subjects`.
- Manifest and evidence-bearing endpoints include the current Archive snapshot.

### Search Design

Single-input unified search that auto-detects:
- **Numeric ID**: Exact match + ILIKE fallback
- **Text query**: Multi-term AND matching with CJK variant expansion per term
- **CJK variants**: ~150 simplified→Japanese kanji pairs, Cartesian product capped at 12 variants
- **Archive aliases**: Selected `infobox` fields and aliases are normalized into `person_search_terms`
- **Fuzzy fallback**: If exact/prefix/contains search leaves room, bounded typo matching runs against compact indexed terms. ASCII/romanized typos use DuckDB `damerau_levenshtein`; CJK/kana typos use a bounded Unicode edit-distance pass over same-prefix, similar-length candidates.

### Display Names

Person payloads include original `name` and optional Archive-provided `nameCn`. The frontend stores `staffGalaxy.personNameMode` in localStorage and supports:

- `original`: show Archive original/Japanese name.
- `cn`: show `nameCn` when present; otherwise fall back to `name`.

When simplified Chinese is primary and the original differs, panels and search pills show the original as secondary context.

### Path Finding

BFS with multi-parent tracking returns all shortest paths. Each path includes node IDs and edge metadata (sharedWorksCount per step). Frontend renders as depth-layered SVG constellation.

The backend BFS expands `person_collaboration_edges`, not `visible_person_edges`.
This preserves hidden low-tier relationships for path and compare workflows.

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

```sql
credit_details          -- credits + subject name + person name
cast_details            -- person_characters expanded
anime_participation_details  -- UNION of staff and cast
person_role_counts      -- credit count per person per role
person_anime_stats      -- per-person summary with tier breakdowns (S/A/B/C/D/EF)
visible_edge_details    -- visible edges + both person names
```

## Frontend Data Flow

```text
App.tsx (mount)
  → loadLevel('global')  →  GET /api/graph/global/nodes + edges
  → buildGraph()         →  Graphology graph instance
  → CosmosGalaxyView     →  WebGL render

User clicks node
  → loadPersonGalaxy(id) →  GET /api/person/{id}/galaxy
  → buildGraph()         →  replace Graphology instance for local galaxy
  → NodePanel opens      →  summary, complete credits, neighbor list

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

The full rebuild:

1. Recreates the DuckDB schema.
2. Ingests Bangumi Archive subjects, persons, positions, staff credits, and cast.
3. Rebuilds complete `person_collaboration_edges`.
4. Rebuilds sparse `visible_person_edges`.
5. Rebuilds `graph_nodes`.
6. Rebuilds `person_search_terms`.
7. Records the current `data_snapshots` row.
8. Writes `reports/data-audit.md`.

Focused migrations for an existing local DB:

```bash
.venv/bin/python scripts/migrate_role_weights.py
.venv/bin/python scripts/migrate_search_index.py
.venv/bin/python scripts/migrate_data_snapshot.py
```

`migrate_role_weights.py` backs up the local DuckDB file before rebuilding
derived role weights, complete edges, visible edges, graph nodes, search terms,
and indexes.

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
