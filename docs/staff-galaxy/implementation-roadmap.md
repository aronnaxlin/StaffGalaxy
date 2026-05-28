# Implementation Roadmap

## Completed

### Phase 1: Data Pipeline ✓
- Bangumi Archive detection and DuckDB import.
- 163 position definitions with normalized roles, tiers, and weights.
- Graph edge and node materialization.
- Data audit with tier comparison reports.

### Phase 2: Backend API ✓
- FastAPI server with live DuckDB queries.
- Graph endpoints: nodes and edges for global/l0/l1 levels.
- Person galaxy endpoint with data-driven layout.
- Person detail and complete credit-history endpoints.
- Unified search with CJK variant mapping, Archive aliases, romanization, kana, numeric IDs, and bounded fuzzy fallback.
- Collaboration detail with per-person roles per shared work.
- BFS shortest path finding with multi-parent tracking over the complete staff collaboration graph.
- Manifest and evidence responses expose Archive snapshot metadata.

### Phase 3: Frontend Core ✓
- React + Cosmos.gl WebGL galaxy renderer.
- Zoom-dependent edge LOD.
- Global graph level switcher for `global`, `l0`, and `l1`, with shareable `/?level=...` URLs.
- Person-centered galaxy view with back-to-global navigation.
- Person detail sidebar with summary stats, complete credit history, expandable collaboration cards, and add-to-compare actions.
- Unified search bar with locked-pill mode.
- Obsidian Graph View visual style.
- Configurable Bangumi person/subject links.
- Person and subject title display preferences backed by localStorage.

### Phase 4: Path Visualization ✓
- ConstellationView — separate page for two-person path finding.
- SVG-based depth-layered node layout with colored Bezier curves.
- All shortest paths displayed with edge labels.
- Shareable `/path?from=...&to=...` routes with browser history support.
- Expandable per-hop evidence.
- Shareable `/compare?from=...&to=...` routes with direct collaboration evidence when degree is 1.

### Phase 5: Scoring Refinement ✓
- Six-tier exponential weight system (S/A/B/C/D/E/F).
- Collaboration score = `SUM(SQRT(w1 × w2))`.
- Graph backbone expanded to S+A+B (weight ≥ 12).
- Complete `person_collaboration_edges` remains separate from sparse renderer `visible_person_edges`.

### Phase 6: Observability & Documentation ✓
- Runtime metrics for API responses and Cosmos graph readiness.
- Production-preview performance baseline in `reports/graph-performance.md`.
- Local rebuild, migration, startup, preview, and verification workflow documented.

## Pending

### Layout Improvement
- Replace `deterministic_spiral_v1` with offline ForceAtlas2 or Leiden/ForceAtlas2.
- Community detection for color assignment.
- Stable coordinates that preserve clusters.

### Voice Cast Integration
- CAST tier currently exists in DB but not rendered in the graph.
- Decide whether voice actors appear as separate layer or are interleaved with staff.

### Performance & Scale
- Bundle splitting: lazy-load Cosmos.gl.
- Server-side pagination for large neighbor lists.
- Time-range filtering on graph edges.
- Broader browser runtime sampling across multiple people and interaction types.

### Deployment
- Static asset serving strategy.
- Database update workflow for new archive snapshots.
- Optional packaged local deployment or container workflow.

### Polish
- Mobile/responsive layout.
- Keyboard shortcuts for common actions.
- Loading states and error boundaries.
- Traditional Chinese display mode if a verified Archive field or trustworthy conversion source is wired.
