# Direction Decisions

## Current Product Bet

Staff Galaxy is an anime staff collaboration explorer. The core question:

```text
Can Bangumi Archive STAFF data be projected as a readable, interactive person graph?
```

Answer: yes. The graph is live with 21K+ nodes and 518K+ edges.

## Decisions Locked

### 1. Default Graph Nodes Are People Only

Default graph shows only real individuals (`person.type = 1`). Companies, groups, and anime works are not default nodes. Works are evidence behind edges.

### 2. Anime Works Stay In The Evidence Layer

Every person relationship must answer:
- Which works did they share?
- What roles did each person hold?
- First and most recent collaboration year?

Works appear in the `NodePanel` sidebar and collaboration detail view, not on the graph.

### 3. Render Sparse Graph, Keep Full Evidence

```text
Full evidence: all credits preserved in DB
Default graph: S+A+B tier people (weight >= 12), filtered edges
```

The graph backbone rule:

```text
sharedWorksCount >= 2 OR top 10 strongest neighbors per endpoint
```

This produces a readable global view while preserving the ability to query any relationship.

### 4. Six-Tier Role Weight System

Positions are weighted exponentially (50 → 0.3) across S/A/B/C/D/E/F tiers based on creative importance in anime production. Collaboration score uses geometric mean: `SQRT(w1 × w2)`.

### 5. Cosmos.gl As Sole Renderer

Sigma.js was removed. Cosmos.gl WebGL handles all graph rendering. Hover labels use DOM overlay (not WebGL text) for performance.

## Stack

### Backend

- Python 3.12 + FastAPI
- DuckDB (single-file database)
- Uvicorn with auto-reload

### Frontend

- Vite + React 19 + TypeScript
- Tailwind CSS 4
- Cosmos.gl (`@cosmos.gl/graph`)
- Graphology (graph data model)

### Architecture Decision

Live API, not static JSON export. Rationale:
- 518K edges would create very large static files.
- API allows dynamic edge filtering per zoom level.
- Person detail and path finding are query-time operations.
- Collaboration detail queries depend on which pair the user selects.

## Main Risks

### Edge Density Risk

With S+A+B tiers, the graph has 518K edges. Zoom-dependent LOD (varying `minSharedWorks` threshold) keeps the view readable. The `linkVisibilityDistanceRange` config also hides edges beyond a certain screen distance.

### Visual Readability Risk

Handled by:
- White/gray dots with warm highlights for degree (Obsidian Graph View style).
- Edge opacity and width driven by `collaborationScore`.
- Node size log-scaled by `visible_weighted_degree`.
- Deterministic spiral layout (placeholder; offline ForceAtlas2 planned).

### Evidence Completeness Risk

Bangumi records may be incomplete. The frontend shows data snapshot info. The API returns `selectionReason` on edges to distinguish strong evidence from top-K inclusion.

### CJK Character Mismatch

`persons.name` stores Japanese kanji. Simplified Chinese queries (e.g., 宫崎骏) wouldn't match 宮崎駿. Solved via `_CJK_MAP` (~150 character pairs) with Cartesian product expansion (capped at 12 variants) in the search endpoint.

## Pending Decisions

- Replace `deterministic_spiral_v1` with ForceAtlas2 or Leiden/ForceAtlas2 offline layout.
- Voice cast (CAST tier) integration into the graph model.
- Community detection and coloring.
- Time-range filtering in the frontend.
