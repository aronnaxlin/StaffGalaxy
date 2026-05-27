# Implementation Roadmap

## Phase 0: Product And Data Direction

Current phase.

Goals:

- Define product semantics.
- Lock MVP boundaries.
- Document data model.
- Document audit requirements.
- Prevent premature frontend implementation.

Outputs:

- `docs/staff-galaxy/product-definition.md`
- `docs/staff-galaxy/data-model-and-architecture.md`
- `docs/staff-galaxy/data-audit-spec.md`
- `docs/staff-galaxy/implementation-roadmap.md`
- `docs/staff-galaxy/mvp-acceptance.md`

## Phase 1: Data Scale Audit

Goal:

确定 Bangumi Archive STAFF 数据投影成人物合作图后的真实规模。

Build:

- Local archive detection.
- DuckDB import.
- Role normalization.
- Candidate graph audit.
- Pruning strategy report.

Do not build:

- Frontend.
- Recommendations.
- Real-time graph layout.

Primary output:

```text
reports/data-audit.md
```

Decision after this phase:

- Default visible role layer: Tier A or Tier A + B.
- Backbone edge strategy.
- Top-K neighbor value.
- Whether initial graph can load all visible nodes and edges at once.

## Phase 2: Mock Graph View

Goal:

Build the interaction model before connecting real data.

Stack:

- React
- TypeScript
- Vite
- Tailwind CSS
- Sigma.js
- Graphology

Use mock JSON under:

```text
public/data/mock/
```

Required interactions:

- Render full-screen galaxy.
- Hover node to show name and neighbors.
- Click person to open detail panel.
- Search one person.
- Compare two people.
- Click edge to show evidence.
- Filter by minimum score and shared works.
- Toggle selected person's neighborhood.

Important:

Mock data must match future production schemas. This prevents throwaway UI code.

## Phase 3: Real Visible Graph Export

Goal:

Generate production JSON files from DuckDB using thresholds selected after Phase 1.

Outputs:

```text
public/data/
├── manifest.json
├── galaxy/nodes.json
├── galaxy/edges-backbone.json
├── galaxy/communities.json
├── persons/person-[id].json
└── search/persons-index.json
```

Build:

- Visible edge computation.
- Node visible degree.
- Node size calculation.
- Community detection.
- Stable offline x/y layout.
- Person detail export.
- Search index export.

Do not:

- Export pair files for every person pair.
- Put anime works into the default graph as nodes.
- Make layout random between builds unless source data changes.

## Phase 4: Real Data Frontend Integration

Goal:

Replace mock data with exported static files.

Required behavior:

- Load `manifest.json` on startup.
- Load galaxy nodes and backbone edges.
- Show snapshot date and data source note.
- Search from `search/persons-index.json`.
- Lazy-load `persons/person-[id].json`.
- Compare two people by intersecting credits.
- Render hidden evidence-only relation as temporary dashed edge.

Side panel must show:

- Person name.
- Major roles.
- Visible collaborators.
- Representative works.
- Shared works for comparison.
- Each person's role in each shared work.
- First and latest collaboration year where available.

## Phase 5: Large Graph Performance And Layered Loading

Goal:

Preserve the feeling of entering a total galaxy without loading all evidence at startup.

Implement:

- Lightweight initial node loading.
- Backbone edge loading for global zoom.
- Community-level edge loading when zoomed or selected.
- Sparse global labels.
- Neighborhood expansion on selection.
- Performance instrumentation.

Instrumentation:

- Initial JSON transfer size.
- Parsing time.
- Graph render time.
- Visible node count.
- Visible edge count.

## Milestone Decisions

After Phase 1:

- Choose role layer.
- Choose top-K.
- Choose minimum score.
- Decide whether community files are needed immediately.

After Phase 2:

- Confirm graph interaction language.
- Confirm detail panel information hierarchy.
- Confirm search and compare flow.

After Phase 3:

- Confirm data size is feasible for static hosting.
- Confirm generated graph is visually readable.
- Confirm evidence lookup works without pair files.

After Phase 4:

- MVP is functionally usable.

After Phase 5:

- MVP is ready for larger public data snapshots.

