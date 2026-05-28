# Staff Galaxy Frontend Rendering

## Current Decision

**Cosmos.gl is the sole renderer.** Sigma.js was evaluated and removed.

```text
DuckDB → FastAPI → React + Cosmos.gl
```

Dual-renderer architecture was tried and abandoned. Cosmos.gl handles all graph rendering: global view, personal galaxy, and zoom/pan interaction.

## Why Cosmos.gl Only

- WebGL GPU rendering handles 21K+ nodes with smooth pan/zoom.
- Zoom-dependent edge LOD keeps the view readable at all scales.
- No label layer needed on the WebGL canvas — hover labels use DOM overlay.
- Removing Sigma.js simplified the bundle (~725 KB → ~636 KB) and eliminated adapter complexity.

## Renderer Configuration

```typescript
const COSMOS_CONFIG = {
  backgroundColor: '#0a0a0f',
  enableSimulation: false,
  spaceSize: 8192,
  fitViewPadding: 0.18,
  pointSizeScale: 0.85,
  pointGreyoutOpacity: 0.03,
  pointOpacity: 0.92,
  scalePointsOnZoom: true,
  scaleLinksOnZoom: false,
  pixelRatio: Math.min(window.devicePixelRatio || 1, 2),
  renderHoveredPointRing: true,
  hoveredPointRingColor: '#f8fafc',
  focusedPointRingColor: '#fef08a',
  linkVisibilityDistanceRange: [35, 180],
}
```

## Edge Level-of-Detail

Zoom-dependent shared-works thresholds filter visible edges:

| Level | Zoom > 0.9 | Zoom > 0.65 | Default |
|---|---|---|---|
| global | 40 | 24 | 12 |
| l0/l1 | 24 | 16 | 12 |
| person | 1 | 1 | 1 |

Edges are rebuilt on zoom end via `applyEdgeDensity()`.

## Hover Performance

Hover labels bypass React state entirely:

- Label DOM element updated via `textContent` + `classList` directly.
- No React re-render on mouseover/mouseout.
- Node ID → label lookup uses a pre-built `Map<string, string>` in the payload (O(1)).
- Cosmos config is a module-level constant, not recreated per render.

## Coordinate System

DB coordinates (`deterministic_spiral_v1`, range ~0–1000) are mapped to Cosmos space:

```typescript
const COSMOS_SPACE_SIZE = 8192
const COSMOS_LAYOUT_SIZE = 4300

// Normalize DB coords into Cosmos [0, 8192] centered at [4096, 4096]
position = SPACE_SIZE / 2 + ((dbCoord - center) / span) * LAYOUT_SIZE
```

## Visual Style

Obsidian Graph View aesthetic:
- White/gray dots with subtle warmth for high-degree nodes.
- Tier A (now S/A) nodes get a slight blue tint.
- Edge colors: warm slate-blue → cyan highlights for strong connections, strength-driven opacity and width.
- Node size: `2.0 + MIN(10.0, LN(1 + weightedDegree) × 1.8)`, log-scaled.
- Center nodes (person view) get larger size (10px).

## Bundle Size

- Main JS chunk: ~636 KB (Cosmos.gl + React + Graphology)
- CSS: ~26 KB (Tailwind)
- Vite's chunk size warning is pre-existing and acceptable for this application.

## What Was Removed

- `@react-sigma/core`, `sigma` — Sigma.js renderer
- `graphology-communities-louvain` — not needed without Sigma
- `graphology-layout-forceatlas2` — offline layout preferred
- `graphology-shortest-path` — path finding done server-side via BFS
- `GalaxyView.tsx`, `GraphEvents.tsx` — Sigma-specific components
