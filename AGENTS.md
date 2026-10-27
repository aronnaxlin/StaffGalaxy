# Staff Galaxy Agent Guide

## Project Summary

Staff Galaxy is an anime staff collaboration graph based on [Bangumi Archive](https://github.com/bangumi/Archive). It displays who worked with whom across the Japanese animation industry.

Core product semantics:

- **Nodes are people** (Bangumi `person.type = 1` real individuals).
- **Edges represent shared anime credits** — two people worked on the same anime.
- **Anime works are evidence behind edges** in the rendered galaxy, never rendered galaxy nodes. In storage they are first-class `:Anime` nodes of the knowledge graph.
- **Global graph stays sparse** for readability; full evidence is always queryable.
- **Person detail and two-person comparison should be as complete as possible.**

Only `subject.type = 2` (anime) is in scope. Companies, groups, and non-anime works are excluded from the default graph.

## Current Architecture

```
Bangumi Archive zip files
  → Python ingest pipeline (staff_galaxy/ingest.py, streams the zip)
  → Neo4j 5 knowledge graph (Docker, docker-compose.yml)
  → FastAPI backend  (staff_galaxy/api.py, Cypher)
  → React 19 + TypeScript + Tailwind CSS 4 + Vite
  → Cosmos.gl WebGL renderer
```

There is no static JSON export pipeline. The frontend talks to the FastAPI backend directly over HTTP.

## Graph Schema

Neo4j 5 Community (APOC + GDS plugins) runs in Docker; connection settings come
from `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` (environment, then `.env`).
Connection and write helpers live in `staff_galaxy/graph_db.py`, whose module
docstring is the authoritative schema.

### Knowledge graph (source of truth)

| Element | Purpose |
|---|---|
| `(:Person {id, name, infobox, career_json, summary})` | Real individuals (`person.type = 1`) |
| `(:Anime {id, name, name_cn, date, year, ...})` | Anime works (`subject.type = 2`) |
| `(:Position {position_id, cn, en, jp, normalized_role, role_tier, role_weight})` | 177 position definitions |
| `(:Character {id, name, role, summary})` | Voice-acted characters |
| `(:Person)-[:CREDITED {position_*, role_tier, role_weight, appear_eps}]->(:Anime)` | Every staff credit (~1M) |
| `(:Person)-[:VOICED {subject_id, ...}]->(:Character)-[:APPEARS_IN]->(:Anime)` | Voice cast |
| `(:Person)-[:HAS_SEARCH_TERM]->(:SearchTerm {norm, compact, kind})` | Search index |
| `(:DataSnapshot {snapshot_id: 'current', archive_name, ...})` | Build metadata |

### Derived galaxy layer (rebuilt by `cli --derived-only`)

| Element | Purpose |
|---|---|
| `(:Person:GalaxyNode {x, y, community_id, visible_degree, node_size, ...})` | People with a credit at weight >= 12 |
| `(:Person)-[:COLLAB {shared_works_count, collaboration_score, significance, selection_reason, ...}]->(:Person)` | Backbone edges (`bicm_significant` / `spanning_forest`), source id < target id |

The complete collaboration graph (~34M person pairs) is deliberately **not**
materialized. Pair evidence (`/api/collaboration`) and shortest paths
(`/api/path`) are derived from `CREDITED` at query time.

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

Collaboration score formula (each person's highest-weight role per work):

```
collaboration_score = SUM( SQRT(w1 × w2) )  for each shared work
```

The geometric mean ensures both people must have significant roles for a high score. Two directors on one show (50) ≈ two key animators on 17 shows (3 × 17 = 51).

Graph backbone: galaxy members are people with a credit at `role_weight >= 12.0` (S+A+B tiers); edges are the BiCM-validated projection of that layer (FDR 0.05 over all person pairs) united with the maximum spanning forest — 23,245 nodes / 107,489 edges on `dump-2026-10-20`. Method and comparison against top-k, disparity filter, hypergeometric SVN, and noise-corrected backbones: `docs/staff-galaxy/data-model-and-architecture.md` "Graph Backbone Selection".

Tier definitions live in `staff_galaxy/roles.py`. Edge and node builders are in `staff_galaxy/visible_edges.py` and `staff_galaxy/graph_nodes.py`.

## API Endpoints

Base URL: `http://localhost:8000`

| Endpoint | Purpose |
|---|---|
| `GET /api/graph/buffers` | Single-segment binary graph (positions/sizes/colors/community/edges), ETag + immutable |
| `GET /api/graph/meta` | Node metadata JSON (id, name variants, degree) — labels.json equivalent |
| `GET /api/person/{id}/galaxy` | A galaxy member's backbone (`COLLAB`) collaborators — the sidebar collaborator list; 404 for people outside the galaxy |
| `GET /api/person/{id}/knowledge-graph?people=10&works=14` | Local `(:Person)-[:CREDITED]->(:Anime)` subgraph: strongest collaborators plus the works linking them, links labelled with roles |
| `GET /api/search/persons?q=...&limit=...` | Unified search (name, CJK variants, Bangumi ID) |
| `GET /api/collaboration/{a}/{b}` | Shared works with roles, years, and scores |
| `GET /api/path/{a}/{b}?max_paths=5` | Shortest path(s) between two people (Cypher `ALL SHORTEST`) |

### Search features

- Single input, no type selector
- Supports: Japanese kanji, simplified Chinese, Bangumi numeric ID
- CJK variant mapping: ~150 simplified→Japanese kanji pairs (e.g., 宫→宮, 骏→駿)
- Multi-term AND matching with per-term CJK variant expansion
- Debounced 180ms in frontend

### Collaboration detail

Returns per-edge metrics plus all shared works with individual role lists. Frontend renders expandable work cards with roles, years, and scores.

### Path finding

Cypher `ALL SHORTEST` over `(:Person)-[:CREDITED]-(:Anime)` (one collaboration hop = two relationships) enumerates shortest paths in the complete graph. Paths that differ only in the linking anime collapse to one person sequence, ranked by weakest step then total score. Rendered in `ConstellationView` as colored SVG Bezier curves across depth-layered node columns.

## Frontend

### Stack

- Vite 8 + React 19 + TypeScript
- Tailwind CSS 4
- Cosmos.gl (`@cosmos.gl/graph`) v3 — WebGL graph renderer (upgraded from 2.6.4;
  see `docs/staff-galaxy/edge-rendering-performance-plan.md` Phase 1)
- react-force-graph-2d — the local knowledge-graph panel (d3-force + canvas;
  drag, zoom, hover and idle redraw pausing come from the library)
- radix-ui (unstyled primitives: Tabs, Popover, Tooltip, Collapsible,
  ToggleGroup, Slider) + lucide-react icons, styled with Tailwind
- Prefer configuring an existing library over hand-rolling renderers or
  interaction code.
- Visual rules: neutral zinc surfaces, a single accent (`ACCENT` in `ui.ts`);
  text ≥ 12px and no dimmer than zinc-500; no letter-spaced CJK labels, no
  tinted borders or gradients. Color in the graph encodes data (communities,
  path series), not decoration.
- No Sigma.js (removed)

### Components

| Component | Purpose |
|---|---|
| `App.tsx` | View routing (galaxy / constellation), global state |
| `CosmosGalaxyView.tsx` | WebGL galaxy renderer: edge LOD, in-place focus, idle render pause |
| `LocalKnowledgeGraph.tsx` | Obsidian-style local Person–Anime graph (react-force-graph) |
| `ConstellationView.tsx` | SVG-based shortest-path visualization |
| `SearchBar.tsx` | Unified search with locked-pill mode and keyboard nav |
| `PersonSidebar.tsx` | Docked person sidebar: tabs 知识图谱 (local graph + SPO triples) / 合作者 / 履历 |
| `ui.ts` | Shared UI tokens — neutral surfaces, one accent `#f5c76b` (amber, same as the galaxy's selection) |

### View modes

- **Galaxy** (`'galaxy'`): Default. Cosmos.gl starfield with pan/zoom and hover labels. Selecting a person (click, search, `/person/:id`) never swaps the scene: the galaxy focuses them in place (circle highlighted, edges repainted, camera glide) and opens the docked PersonSidebar (the galaxy canvas narrows so the camera centers on the visible area). Background click clears the selection.
- Whole-galaxy force simulation was measured and rejected: ~11 fps on an M1 MacBook Air and it scrambles the Leiden layout. Motion lives in the small local knowledge graph instead.
- **Constellation** (`'constellation'`): Two-person path finding. Left sidebar with search inputs, right SVG canvas showing all shortest paths as colored Bezier curves.

### Key design decisions

- Single global graph, no levels: `App.tsx` loads `/api/graph/buffers` +
  `/api/graph/meta` once via `data/graphBuffers.ts` (immutable-cached, keyed by
  archive name + geometry fingerprint). Level UI was replaced by client-side
  min-degree and edge-budget sliders in `CosmosGalaxyView`. The separate
  "person galaxy" scene was removed in favor of in-place focus.
- `data/cosmosPayload.ts` builds the Cosmos payload as direct typed-array views
  over the binary buffer (no JSON rows). Edge order is shared_works_count DESC
  (server) so LOD is a prefix.
- Community coloring: server ships a neutral gray base color; the client applies
  a low-saturation golden-angle hue per Leiden `community` id
  (`communityColor` in `cosmosPayload.ts`).
- Hover labels use DOM direct manipulation (not React state) for smooth performance at 21K+ nodes.
- Cosmos config is a module-level constant, avoiding re-creation on every render.
- Edge LOD: only a strength-sorted *prefix* of the edges is uploaded
  (`setLinks`), sized by zoom (`edgeBudgetForZoom`: 80K / 50K / 30K) times the
  quality level; the selected person's edges beyond the prefix are appended.
  Do NOT go back to uploading every edge and zeroing widths: cosmos.gl pads each
  link with a 0.5 px smoothing band, so zero-width links are still rasterized
  end to end — measured under software rendering, 20K "visible" of 107K
  uploaded cost exactly as much as all 107K (0.7 fps). A prefix re-upload takes
  5–17 ms; an earlier ~0.5 s pan hitch was misattributed to it.
- Adaptive render quality (`QUALITY_LEVELS`): frame times are sampled only while
  cosmos.gl renders; a median above 26 ms steps down (pixel ratio 2 → 1.5 → 1,
  then edge scale 1 → 0.6 → 0.3 → 0.12 → 0.05), sustained headroom steps back up
  but never into a level that proved slow this session. The level persists in
  localStorage; software rasterizers (SwiftShader / llvmpipe) start at the floor.
  Under SwiftShader this takes the zoomed-out galaxy from 0.8 to ~49 fps.
- GPU benchmark: `frontend/scripts/gpu-bench.mjs` (CDP, no deps) measures render
  cost per variant; `?debug` exposes `window.__galaxyDebug` for it. Run
  `node scripts/gpu-bench.mjs --url http://127.0.0.1:4173/ --launch /usr/bin/chromium --swiftshader`
  for the software floor, or `--port` against a visible Chrome on a real device.
  Headless Chromium on Linux falls back to SwiftShader even with a GPU present.
- Never call a function that creates a WebGL context during render (e.g. as a
  `useRef(...)` argument): browsers cap live contexts and evict the oldest —
  the galaxy's own — which renders the canvas black.
- Idle render pause: cosmos.gl redraws every frame forever; `wake()` in
  `CosmosGalaxyView` pauses its loop after 1.5 s without input via the
  TS-private `startFrames`/`stopFrames` (feature-detected). Only restart when
  `requestAnimationFrameId` is 0 — hover callbacks run inside a frame, and
  restarting there forks a second render loop (measured: hover fell to 39 fps).
- `fitViewOnInit` is off: its delayed fit would override the camera glide to a
  deep-linked `/person/:id`.
- Hover highlighting is v3 config-driven (`highlightedPointIndices` /
  `highlightedLinkIndices`), resolved via a precomputed `pointToLinkIndices`
  incidence map — O(degree), not O(edges). cosmos.gl's own
  `getConnectedLinkIndices(pointIndices)` requires BOTH endpoints of a link to be
  in the given set ("edges within a selection"); it returns nothing useful for a
  single hovered point, which is why this project has its own incidence map
  instead.
- cosmos.gl v3 color buffers (`setPointColors`/`setLinkColors`) are RGBA
  normalized to `[0, 1]` — NOT the `0-255` RGB range v2 used. Config-level array
  colors (`linkDefaultColor`, etc.) also changed to `0-1` for RGB (alpha was
  already `0-1` in both versions).
- `setConfig()` in v3 resets the entire config to defaults before applying —
  always use `setConfigPartial()` for incremental updates.
- `selectPointByIndex()`/`unselectPoints()` were removed in v3; selection ring
  is driven by `focusedPointIndex` alone.
- Pixel ratio capped at 2 for performance on retina displays.
- `pixelRatio: Math.min(window.devicePixelRatio \|\| 1, 2)`
- Vite alias for `gl-bench` (a cosmos.gl v3 transitive dep) forces resolution to
  its ESM build — its `browser` field points to a UMD bundle with no
  `export default`, which fails Vite/rolldown's production build otherwise. See
  `vite.config.ts`.

### Performance characteristics

- (Measured before the BiCM backbone, which cut edges ~5× to 107,489.) Single global graph as of `dump-2026-06-30`: 21,383 nodes / 529,310 edges,
  shipped as `/api/graph/buffers` (7.8 MB raw / 1.84 MB gzip) +
  `/api/graph/meta` (2.78 MB / 566 KB gzip). `graph-buffers-loaded` metric
  ≈1.2–2.1 s cold in headless Chrome; canvas visible ≈2.25–5 s end-to-end on
  SwiftShader (device init dominates; real GPUs are faster). See
  `reports/graph-performance.md` "Phase 2+3".
- Layout is `hier_leiden_fr_v1` (Leiden + inter-cluster FR + circle packing +
  intra-cluster FR/DrL, `staff_galaxy/layout.py`): 481 communities, 58.4% of
  edges intra-community, mean edge length 11.2 vs 3,717 span, 139 s build.
- Zoom-dependent edge budget (prefix slice of the strength-sorted arrays) keeps
  visible edges manageable without discarding data; a slider overrides it
  manually up to the full 529,310.
- cosmos.gl v3's luma.gl (WebGL2) port is heavier than the old regl-based v2:
  the lazy Cosmos chunk is ~655 KB (~151 KB gzip).
- **Dev-server (`npm run dev`) load times are not representative** — React 19
  StrictMode double-invokes mount effects in development. Always measure against
  a production build, matching this project's existing convention in
  `reports/graph-performance.md`.

## Commands

### Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

### Start Neo4j

```bash
docker compose up -d neo4j        # Browser: http://localhost:7474
```

### Rebuild the knowledge graph from archive (wipes the graph)

```bash
.venv/bin/python -m staff_galaxy.cli
```

### Rebuild derived layer only (role weights / layout changed; no re-ingest)

```bash
.venv/bin/python -m staff_galaxy.cli --derived-only
```

### Run backend tests (throwaway Neo4j on port 7688; tests wipe it)

```bash
docker compose --profile test up -d neo4j-test
.venv/bin/python -m unittest -v tests.test_api_complete_graph
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
    neo4j/                                  # Neo4j data, logs, plugins (Docker volume)
```

Raw and processed data, and `.env`, are git-ignored.

## Reports

```
reports/
  data-audit.md             # Latest database snapshot statistics
  archive-feasibility.md    # Original archive exploration
  position-role-audit.md    # Position classification audit
```

Note: reports may be stale (performance reports predate the Neo4j migration). Trust the code and graph over report numbers.

## Design Docs Precedence

`docs/staff-galaxy/` holds design and research docs. They are not all current
to the same date — when they conflict, newer supersedes older:

- **`docs/staff-galaxy/edge-rendering-performance-plan.md` is the current
  authoritative plan for graph rendering/performance work** (nebula edge
  rendering, cosmos.gl version, node/edge transport format, layout
  algorithm). Its Phase 1/2/3 are implemented — the three-level
  global/l0/l1 system and the JSON graph endpoints are gone, replaced by a
  single binary graph and the `hier_leiden_fr_v1` layout; Phase 4 (label
  polish) and Phase 5 (26M-edge contingency) remain proposals.
- `docs/staff-galaxy/frontend-rendering-research.md` and
  `reports/graph-performance.md` describe the *pre-rewrite* architecture
  (Cosmos.gl 2.6.4, JSON transport, three-tier global/l0/l1 levels,
  spiral layout) wherever they have not been annotated — do not use them
  to justify keeping the old three-tier level system or the JSON graph
  endpoints.
- If you are implementing part of the plan, update these older docs (or
  mark the superseded sections) as you go, rather than leaving
  contradictory docs for the next agent to untangle.

## Collaboration Rules

- Keep changes scoped to the task at hand.
- Prefer editing existing files over creating new ones.
- Do not rewrite data semantics without updating this file.
- Preserve full evidence even when hiding relationships from the default graph.
- Treat default graph visibility as a performance/readability choice, not as truth.
- Prefer explicit, verifiable Cypher checks after data changes.
- Restart the backend (`uvicorn --reload`) after Python changes.
- Vite HMR handles frontend changes automatically.
- Never introduce anime recommendation features or render anime as galaxy nodes (anime are knowledge-graph nodes in storage only).
- No backwards-compatibility shims — delete, don't deprecate.
