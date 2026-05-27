# Staff Galaxy Frontend Rendering Research

## Current Decision

Use a renderer-adapter architecture instead of betting the whole product on one graph library.

```text
DuckDB API
  -> graph protocol / Graphology model
  -> renderer adapters
      -> Sigma.js for labels, selection, local exploration
      -> cosmos.gl for GPU-heavy global galaxy experiments
      -> optional 3D renderer later, not default
```

## Candidate Matrix

| Renderer | Best Use | Strengths | Risks |
| --- | --- | --- | --- |
| Sigma.js + Graphology | Default product interaction and local exploration | Mature React path, labels, reducers, selection, search state, good graph model | Large dense global views still require aggressive LOD |
| cosmos.gl / `@cosmos.gl/graph` | Global "total galaxy" GPU canvas | WebGL point/link arrays, fast pan/zoom, useful for thousands of sparse person nodes | No built-in label layer, needs adapter work for coordinates, focus state, hit labels, evidence UI |
| 3d-force-graph / Three.js | Optional 3D lab mode | Depth, visual drama, intuitive orbit for demos | Occlusion hurts reading names and comparing evidence; should not be the default Staff Galaxy workflow |
| Custom Canvas/WebGL | Only if library candidates fail | Full control over LOD and labels | More engineering cost before product semantics stabilize |

References checked:

- [cosmosgl/graph](https://github.com/cosmosgl/graph): GPU/WebGL graph renderer, MIT.
- [Sigma.js](https://github.com/jacomyal/sigma.js): WebGL graph renderer, MIT.
- [Graphology](https://github.com/graphology/graphology): graph data model and algorithms, MIT.
- [3d-force-graph](https://github.com/vasturiano/3d-force-graph): ThreeJS 3D force graph, MIT.

## Browser Findings

I wired a Cosmos POC behind `?renderer=cosmos` and the top-bar renderer toggle.

Observed:

- The Cosmos canvas renders the same DB-backed data through the existing API.
- The current global API layer returns `16,800` Tier A person nodes and `1,968` strong collaboration edges with `sharedWorksCount >= 12`.
- Cosmos uses zoom-dependent edge LOD:
  - far view: `sharedWorksCount >= 40`;
  - mid view: `sharedWorksCount >= 24`;
  - near view: `sharedWorksCount >= 12`.
- The default Cosmos entry can focus a known person, currently Bangumi person `94` 庵野秀明, so the app does not need to start by forcing a full graph overview.
- Cosmos needs a coordinate adapter. The current DB `deterministic_spiral_v1` coordinates are not in Cosmos' expected space; mapping them into an `8192` canvas centered around `4096,4096` fixes the blank canvas.
- Zoom/pan feels smoother than the current Sigma global view.
- Labels are the main missing piece. Cosmos is promising as a global starfield renderer, but Staff Galaxy still needs a separate label/selection/evidence layer.
- The production build now warns that the main JS chunk is about `725 kB`. If we keep both renderers, Cosmos should be lazy-loaded.
- The biggest visual blocker is not the renderer anymore; it is the placeholder layout. `deterministic_spiral_v1` produces a regular point field, not a semantic galaxy. The next backend/data task should compute an offline graph layout and store stable coordinates in DuckDB.

## 3D Position

3D is worth researching as a separate mode, not as the default.

Use it for:

- "explore depth" demo mode.
- Dense community overviews.
- Visual storytelling.

Avoid it for default work:

- person name reading;
- two-person comparison;
- evidence inspection;
- stable shareable screenshots.

The better near-term plan is a high-quality 2D global galaxy plus local expansion, then a 3D experiment after the data API and local evidence panel are solid.

## Recommended Next Architecture

```text
frontend/src/graph/
  protocol/
    graph-level.ts
    graph-node.ts
    graph-edge.ts
  adapters/
    sigma-adapter.tsx
    cosmos-adapter.tsx
  controls/
    search-controller.ts
    selection-controller.ts
    level-controller.ts
  layout/
    normalize-cosmos-coordinates.ts
    offline-layout-contract.ts
```

Immediate next steps:

1. Lazy-load Cosmos so Sigma remains the small default bundle.
2. Move the coordinate normalization into a named adapter helper.
3. Export or compute better offline layout coordinates from the backend. The current spiral placeholder is okay for plumbing, not for final reading.
4. Keep Sigma as the local/detail renderer while Cosmos is evaluated for global L0/L1.
5. Add a label overlay strategy for Cosmos: selected node, hovered node, and top-N high-degree names only.
