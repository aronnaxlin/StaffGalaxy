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
| `/api/search/persons` | GET | Search with CJK variant expansion |
| `/api/collaboration/{a}/{b}` | GET | Shared works with per-person roles |
| `/api/path/{a}/{b}` | GET | BFS shortest paths between two people |

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
  → swapGraph()          →  mutate existing Graphology instance
  → NodePanel opens      →  sidebar with neighbor list

User expands collaboration
  → loadCollaborationDetail(a, b) → GET /api/collaboration/{a}/{b}
  → shows shared works, roles, years

User opens constellation
  → ConstellationView    →  two SearchBars
  → loadShortestPath(a,b) → GET /api/path/{a}/{b}
  → SVG rendering        →  Bezier curves connecting depth-layered nodes
```
