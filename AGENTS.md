# Staff Galaxy Agent Guide

## Project Summary

Staff Galaxy is an anime staff collaboration graph based on [Bangumi Archive](https://github.com/bangumi/Archive). It displays who worked with whom across the Japanese animation industry.

Core product semantics:

- **Nodes are people** (Bangumi `person.type = 1` real individuals).
- **Edges represent shared anime credits** — two people worked on the same anime.
- **Anime works are evidence behind edges**, not default graph nodes.
- **Global graph stays sparse** for readability; full evidence is always queryable.
- **Person detail and two-person comparison should be as complete as possible.**

Only `subject.type = 2` (anime) is in scope. Companies, groups, and non-anime works are excluded from the default graph.

## Current Architecture

```
Bangumi Archive zip files
  → Python ingest pipeline (DuckDB)
  → FastAPI backend  (staff_galaxy/api.py)
  → React 19 + TypeScript + Tailwind CSS 4 + Vite
  → Cosmos.gl WebGL renderer
```

There is no static JSON export pipeline. The frontend talks to the FastAPI backend directly over HTTP.

## Database

```
data/processed/staff_galaxy.duckdb
```

### Core Tables

| Table | Purpose |
|---|---|
| `subjects` | Anime works (type=2 only for graph) |
| `persons` | Real individuals (type=1) |
| `characters` | Voice acting characters |
| `staff_positions` | 163 position definitions with tiers and weights |
| `credits` | Every person→subject→position record |
| `person_characters` | Voice cast records |
| `visible_person_edges` | Pre-computed graph edges |
| `graph_nodes` | Pre-computed node positions and metrics |

### Views

| View | Purpose |
|---|---|
| `credit_details` | credits + subject name + person name |
| `cast_details` | person_characters + subject name + person name |
| `anime_participation_details` | UNION of staff and cast participations |
| `person_role_counts` | Credit count per person per role |
| `person_anime_stats` | Per-person anime credit summary with tier breakdowns |
| `visible_edge_details` | visible_person_edges + both person names |

## Role Tier System

163 positions classified into 6 tiers weighted exponentially for collaboration scoring:

| Tier | Weight | Count | Examples |
|---|---|---|---|
| **S** | 50.0 | 2 | 导演, 总导演 |
| **A** | 25.0 | 7 | 原作, 系列构成, 人物设定, 总作画监督, 动画制片人, 副导演, 联合导演 |
| **B** | 12.0 | 15 | 脚本, 音乐, 分镜, 演出, 制片人, 企画, 人物原案 |
| **C** | 6.0 | 40 | 美术监督, 摄影监督, 音响监督, 作画监督, 色彩设计, 3D导演 |
| **D** | 3.0 | 76 | 原画, 第二原画, 背景美术, 摄影, 道具设计, 主题歌 |
| **E** | 1.0 | 15 | 补间动画, 数码绘图, 制作进行, 宣传 |
| **F** | 0.3 | 6 | 特别鸣谢, 协力, 製作 |

Collaboration score formula:

```
collaboration_score = SUM( SQRT(w1 × w2) )  for each shared work
```

The geometric mean ensures both people must have significant roles for a high score. Two directors on one show (50) ≈ two key animators on 17 shows (3 × 17 = 51).

Graph backbone uses `role_weight >= 12.0` (S+A+B tiers), producing ~21,006 nodes and ~518,581 edges.

Tier definitions live in `staff_galaxy/roles.py`. Edge and node builders are in `staff_galaxy/visible_edges.py` and `staff_galaxy/graph_nodes.py`.

## API Endpoints

Base URL: `http://localhost:8000`

| Endpoint | Purpose |
|---|---|
| `GET /api/graph/{level}/nodes` | Graph nodes for `global`, `l0`, or `l1` level |
| `GET /api/graph/{level}/edges` | Graph edges for `global`, `l0`, or `l1` level |
| `GET /api/person/{id}/galaxy` | Person-centered galaxy with data-driven layout |
| `GET /api/search/persons?q=...&limit=...` | Unified search (name, CJK variants, Bangumi ID) |
| `GET /api/collaboration/{a}/{b}` | Shared works with roles, years, and scores |
| `GET /api/path/{a}/{b}?max_paths=5` | Shortest path(s) between two people (BFS) |

### Search features

- Single input, no type selector
- Supports: Japanese kanji, simplified Chinese, Bangumi numeric ID
- CJK variant mapping: ~150 simplified→Japanese kanji pairs (e.g., 宫→宮, 骏→駿)
- Multi-term AND matching with per-term CJK variant expansion
- Debounced 180ms in frontend

### Collaboration detail

Returns per-edge metrics plus all shared works with individual role lists. Frontend renders expandable work cards with roles, years, and scores.

### Path finding

BFS with multi-parent tracking returns all shortest paths between two people. Rendered in `ConstellationView` as colored SVG Bezier curves across depth-layered node columns.

## Frontend

### Stack

- Vite 8 + React 19 + TypeScript
- Tailwind CSS 4
- Cosmos.gl (`@cosmos.gl/graph`) — WebGL graph renderer
- Graphology — graph data model
- No Sigma.js (removed)

### Components

| Component | Purpose |
|---|---|
| `App.tsx` | View routing (galaxy / constellation), global state |
| `CosmosGalaxyView.tsx` | WebGL galaxy renderer with zoom-dependent edge LOD |
| `ConstellationView.tsx` | SVG-based shortest-path visualization |
| `SearchBar.tsx` | Unified search with locked-pill mode and keyboard nav |
| `NodePanel.tsx` | Person detail sidebar with expandable collaboration cards |

### View modes

- **Galaxy** (`'galaxy'`): Default. Cosmos.gl starfield with pan/zoom, hover labels, click-to-focus.
- **Constellation** (`'constellation'`): Two-person path finding. Left sidebar with search inputs, right SVG canvas showing all shortest paths as colored Bezier curves.

### Key design decisions

- Hover labels use DOM direct manipulation (not React state) for smooth performance at 21K+ nodes.
- Cosmos config is a module-level constant, avoiding re-creation on every render.
- Edge LOD: shared-works threshold varies with zoom level to keep the view readable.
- Pixel ratio capped at 2 for performance on retina displays.
- `pixelRatio: Math.min(window.devicePixelRatio \|\| 1, 2)`

### Performance characteristics

- Initial bundle: ~636 KB (Cosmos.gl is the largest dependency)
- 21K nodes, 518K edges in global view
- Zoom-dependent edge filtering keeps visible edges manageable
- No full-graph force layout at startup

## Commands

### Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

### Rebuild database from archive

```bash
.venv/bin/python -m staff_galaxy.cli
```

### Update role weights only (no re-ingest)

```bash
.venv/bin/python scripts/migrate_role_weights.py
```

### Start backend

```bash
.venv/bin/uvicorn staff_galaxy.api:app --reload --port 8000
```

### Start frontend dev server

```bash
cd frontend && npm run dev
```

### Type-check frontend

```bash
cd frontend && npm run build
# or just type-checking:
cd frontend && npx tsc --noEmit
```

## Local Data Layout

```
data/
  raw/
    dump-*.zip                              # Bangumi Archive dump
    bangumi-archive/aux/latest.json         # Archive metadata
    bangumi-common/subject_staffs.yml       # Position constants
  processed/
    extracted/                              # Unzipped jsonlines
    staff_galaxy.duckdb                     # Built database
```

Raw and processed data are git-ignored.

## Reports

```
reports/
  data-audit.md             # Latest database snapshot statistics
  archive-feasibility.md    # Original archive exploration
  position-role-audit.md    # Position classification audit
```

Note: reports may be stale. Trust the code and database over report numbers.

## Collaboration Rules

- Keep changes scoped to the task at hand.
- Prefer editing existing files over creating new ones.
- Do not rewrite data semantics without updating this file.
- Preserve full evidence even when hiding relationships from the default graph.
- Treat default graph visibility as a performance/readability choice, not as truth.
- Prefer explicit, verifiable SQL checks after data changes.
- Restart the backend (`uvicorn --reload`) after Python changes.
- Vite HMR handles frontend changes automatically.
- Never introduce anime recommendation features or anime-as-nodes.
- No backwards-compatibility shims — delete, don't deprecate.
