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
- Unified search with CJK variant mapping.
- Collaboration detail with per-person roles per shared work.
- BFS shortest path finding with multi-parent tracking.

### Phase 3: Frontend Core ✓
- React + Cosmos.gl WebGL galaxy renderer.
- Zoom-dependent edge LOD.
- Person-centered galaxy view with back-to-global navigation.
- Person detail sidebar with expandable collaboration cards.
- Unified search bar with locked-pill mode.
- Obsidian Graph View visual style.

### Phase 4: Path Visualization ✓
- ConstellationView — separate page for two-person path finding.
- SVG-based depth-layered node layout with colored Bezier curves.
- All shortest paths displayed with edge labels.

### Phase 5: Scoring Refinement ✓
- Six-tier exponential weight system (S/A/B/C/D/E/F).
- Collaboration score = `SUM(SQRT(w1 × w2))`.
- Graph backbone expanded to S+A+B (weight ≥ 12).

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

### Deployment
- Production build configuration.
- Static asset serving strategy.
- Database update workflow for new archive snapshots.

### Polish
- Mobile/responsive layout.
- Keyboard shortcuts for common actions.
- URL state for shareable views (selected person, constellation pair).
- Loading states and error boundaries.
