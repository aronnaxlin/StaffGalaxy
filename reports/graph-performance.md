# Graph Performance

Last updated: 2026-05-28 18:25 Asia/Shanghai

## Data Snapshot

- Archive zip: `data/raw/dump-2026-05-19.210434Z.zip`.
- Archive created at: `2026-05-19T21:04:35Z`.
- Archive zip size: 404,069,971 bytes.
- DuckDB path: `data/processed/staff_galaxy.duckdb`.
- Data snapshot table: `current` / `dump-2026-05-19.210434Z.zip`.
- Complete staff collaboration edges: 26,017,438.
- Complete edge evidence pairs: 41,472,689 shared-work pairs.
- Visible renderer edges: 518,581.
- Graph nodes: 21,006.
- Person infobox rows populated from Archive: 93,579.
- Search terms: 253,625 terms across 83,565 real people after adding Archive-provided traditional Chinese name fields (`name`: 83,565, `infobox`: 170,060).

## API Manifest

Measured against `uvicorn staff_galaxy.api:app --host 127.0.0.1 --port 8001`.

| Level | Nodes | Edges | Filter |
|---|---:|---:|---|
| global | 21,006 | 3,797 | `min_degree=0`, `min_shared=12` |
| l0 | 1,477 | 134,931 | `min_degree=150`, `min_shared=1` |
| l1 | 4,422 | 119,441 | `min_degree=50`, `min_shared=3` |

`/api/manifest` now includes the current Archive snapshot metadata. Person detail, person credits, and collaboration evidence responses return the same snapshot under `source.snapshot`.

## Build Size

`cd frontend && npm run build`

| Asset | Size | Gzip |
|---|---:|---:|
| `dist/index.html` | 0.45 KB | 0.29 KB |
| `dist/assets/index-Cy6sXnYt.css` | 30.81 KB | 6.51 KB |
| `dist/assets/index-Nuw5OKWp.js` | 293.85 KB | 83.52 KB |
| `dist/assets/CosmosGalaxyView-hjPb3uMa.js` | 362.17 KB | 105.94 KB |
| `dist/assets/ConstellationView-BMVnEofN.js` | 11.54 KB | 4.20 KB |

The previous single main JavaScript bundle was `661.94 KB` / `189.53 KB gzip`.
Cosmos.gl now lives in a lazy route chunk, and the main app bundle is below Vite's default 500 KB warning threshold.

## Runtime Metrics

The frontend now records lightweight browser runtime metrics in
`window.__staffGalaxyMetrics` and dispatches `staff-galaxy:metric` events for:

- `api-response`: URL, HTTP status, request duration, and success flag.
- `cosmos-ready`: graph level, node count, total edges, visible edges, and current edge cutoff after Cosmos receives graph data.

Measured against production preview:

```bash
cd frontend && npm run build
cd frontend && npm run preview -- --host 127.0.0.1 --port 4173
```

Backend was the local FastAPI server on `http://127.0.0.1:8000`.

Additional production-preview smoke after adding priority labels:

- `/` rendered sparse, non-overlapping high-priority labels over the global Cosmos graph and reported no browser console warnings/errors.
- `/person/1040` rendered sparse labels for `宮崎駿` and key collaborators without covering the side panel; console remained clean.

Additional production-preview smoke after Bangumi-inspired panel refactor:

- `/` rendered the refreshed top control rail and search dropdown for `宫崎骏`.
- `/person/1040` rendered the refreshed right-side person panel, filters, collaborator rows, and footer link without console warnings/errors.

Additional production-preview smoke after adding the global data-source notice:

- `/` rendered `数据快照 2026-05-19`, expanded to show `dump-2026-05-19.210434Z.zip`, the Archive source link, and the incomplete-record notice.
- `/person/1040` rendered the same notice left of the right-side panel without obscuring the person detail panel; console remained clean.

| Route / action | Main evidence | Browser/API timing |
|---|---|---:|
| `/` | `cosmos-ready`, global, 21,006 nodes, 3,797 total edges, 144 visible at cutoff 40 | 824.4 ms from navigation start |
| `/api/graph/global/nodes` | 3.88 MB, 21,006 rows | 236.2 ms via direct API timing; 355.2 ms through preview browser proxy |
| `/api/graph/global/edges` | 0.59 MB, 3,797 rows | 33.5 ms via direct API timing; 203.1 ms through preview browser proxy |
| `/api/graph/l0/nodes` | 0.27 MB, 1,477 rows | 31.1 ms |
| `/api/graph/l0/edges` | 19.44 MB, 134,931 rows | 376.0 ms |
| `/api/graph/l1/nodes` | 0.81 MB, 4,422 rows | 75.5 ms |
| `/api/graph/l1/edges` | 17.72 MB, 119,441 rows | 288.0 ms |
| `/?level=l0` | `cosmos-ready`, l0, 1,477 nodes, 134,931 total edges, 318 visible at cutoff 24 | 1,157.5 ms from navigation start |
| toolbar switch to `/?level=l1` | `cosmos-ready`, l1, 4,422 nodes, 119,441 total edges, 526 visible at cutoff 24 | 1,987.3 ms from first navigation start |
| `/person/1040` | `cosmos-ready`, person, 94 nodes, 93 edges | 185.9 ms from navigation start |
| `/api/person/1040/detail` | summary stats and recent works | 92.5 ms through preview browser proxy |
| Expand `宮崎駿` ↔ `鈴木敏夫` collaboration | `/api/collaboration/1040/2215` | 189.7 ms through preview browser proxy |
| `/compare?from=1040&to=2215` | direct compare, 31 shared works | 402.1 ms to collaboration evidence; path API 217.4 ms |
| `/path?from=1040&to=11706` | 2-degree non-direct path | 3,049.0 ms to rendered path; path API 3,015.9 ms |

Production preview console check after this measurement returned no warnings or errors.

Additional production-preview route smoke:

- Direct `/?level=l0` opened the core graph and preserved the URL.
- Toolbar `细节视图` switched to `/?level=l1` and rendered the detail graph.
- `/person/1040` → `返回全量星系` returned to `/` without the side panel covering the control.
- Console check returned no warnings or errors.
- Bangumi-inspired panel refactor smoke:
  - `/person/1040` rendered the redesigned toolbar and right detail panel without overlap at 1280×900.
  - Search for `宫崎` opened the redesigned result dropdown with degree, Bangumi ID, and external-link affordances.
  - `/compare?from=1040&to=2215` rendered the redesigned direct comparison sidebar with 31 shared works.
  - `/path?from=1040&to=11706` rendered the redesigned non-direct path sidebar and evidence controls.
  - Console check returned no warnings or errors.
- Traditional Chinese person-name smoke:
  - Rebuilt `person_search_terms` with `scripts/migrate_search_index.py`.
  - Search `神前曉` returned `3287 / 神前暁`, `nameCn=神前晓`, `nameTw=神前曉`.
  - `/api/graph/global/nodes` payloads include `nameTw`.
  - Browser production preview showed the `繁中` toolbar toggle, re-rendered the search row as `神前曉` / `神前暁`, and opened `/person/3287`.
  - Console check returned no warnings or errors.
- Personal-galaxy filter smoke:
  - `/person/1040` initially loaded the default personal galaxy, then `边强度 3+` and `显示数 60` triggered `/api/person/1040/galaxy?limit=60&min_shared=3`.
  - The renderer legend updated to `min shared works: 3`, with 30 people and 29 edges in the filtered graph.
  - `合作者职位 SAB` displayed 29 loaded collaborators; `合作者职位 CD` displayed the empty-state message for this sample.
  - `时间 近10年` narrowed the list to 6 / 29 collaborators.
  - Console check returned no warnings or errors.
- Personal-galaxy multi-hop smoke:
  - `/person/1040` rendered 94 people and 93 edges before expansion.
  - Expanding `鈴木敏夫` triggered `/api/person/2215/galaxy?limit=36&min_shared=1`.
  - The merged personal graph rendered 103 people and 128 edges.
  - Collapsing the expansion restored the original 94 people and 93 edges.
  - Console check returned no warnings or errors.
- Lazy route chunk smoke:
  - `/` loaded `index-B41htz54.js` plus `CosmosGalaxyView-D9fv_E44.js` and rendered the global graph.
  - `/path?from=1040&to=2215` loaded `index-B41htz54.js` plus `ConstellationView-wqffr0dd.js` and rendered direct collaboration evidence.
  - Console check returned no warnings or errors.

Search distribution sample against the local FastAPI server (`5` runs per query):

| Query | Median | Max observed | Notes |
|---|---:|---:|---|
| `zzzz-not-a-person-xyz` | 65.0 ms | 152.5 ms | no-result ASCII query |
| `不存在的人物测试` | 53.6 ms | 65.7 ms | no-result CJK query |
| `Miyazki Hayao` | 72.9 ms | 100.4 ms | romanized typo, intended person first |
| `宫崎俊` | 69.1 ms | 74.5 ms | ambiguous one-edit CJK typo |
| `1040` | 49.4 ms | 50.3 ms | numeric ID exact query |

## Smoke Timings

- Direct Python API search timings against `data/processed/staff_galaxy.duckdb`:

| Query | First result | Time |
|---|---|---:|
| `Hayao Miyazaki` | `1040` / `宮崎駿` | 72.52 ms |
| `Miyazaki Hayao` | `1040` / `宮崎駿` | 43.25 ms |
| `照樹務` | `1040` / `宮崎駿` | 35.60 ms |
| `みやざき はやお` | `1040` / `宮崎駿` | 43.46 ms |
| `宫崎骏` | `1040` / `宮崎駿` | 85.05 ms |
| `宮崎駿` | `1040` / `宮崎駿` | 37.16 ms |
| `1040` | `1040` / `宮崎駿` | 37.05 ms |
| `Miyazki Hayao` | `1040` / `宮崎駿` | 191.81 ms |
| `Hayao Miyazki` | `1040` / `宮崎駿` | 75.97 ms |
| `Hyao Miyazaki` | `1040` / `宮崎駿` | 76.56 ms |
| `宫崎俊` | Intended `1040` appears in top 3; one-edit CJK ranking is ambiguous | 72.90 ms |
| `鈴木敏雄` | Intended `2215` appears in top 3; one-edit CJK ranking is ambiguous | 73.04 ms |

- Browser smoke check on `http://127.0.0.1:5173/`:
  - Search for `Hayao Miyazaki` rendered `宮崎駿 93 #1040`; selecting it opened `/person/1040`.
  - Search for `照樹務` rendered `宮崎駿 93 #1040`.
  - Browser console check after alias-search smoke returned no warnings or errors.
  - `/person/1040` rendered snapshot label `dump-2026-05-19.210434Z.zip · 2026-05-19` in the person detail source footer.
  - `/path?from=1040&to=2215` rendered the same snapshot label in direct collaboration evidence and expanded hop evidence.
  - Browser console check after snapshot smoke returned no warnings or errors.
  - Person display-name mode smoke:
    - `/person/1040` switched to `简中`, showing `宫崎骏` primary and `宮崎駿` secondary.
    - Neighbor labels switched to Archive-provided simplified names such as `铃木敏夫`.
    - `/path?from=1040&to=2215` showed simplified endpoint pills, path labels, and direct evidence labels.
    - Browser console check after name-mode smoke returned no warnings or errors.
  - Global graph loaded with 21,006 people and 3,797 visible global edges.
  - Search for `宫崎骏` returned `宮崎駿` and opened the person-centered graph.
  - Expanded `宮崎駿` ↔ `鈴木敏夫` collaboration detail rendered subject links and switched title mode from original to Chinese.
  - Constellation view rendered path person links for `宮崎駿` and `鈴木敏夫`.
  - Direct comparison in Constellation rendered `宮崎駿` ↔ `鈴木敏夫` evidence with 31 works and Bangumi subject links.
  - Non-direct comparison rendered `宮崎駿` ↔ `飯飼一幸` as no direct collaboration evidence with a 2-degree path and no collaboration 404 in the browser console.
  - Person detail summary for `宮崎駿` rendered 79 anime, 190 position records, 1963–2023 year range, common roles, recent works, and Bangumi subject links.
  - Complete credit history expansion for `宮崎駿` rendered grouped subject links and raw role chips for 190 position records.
  - Path hop evidence expansion rendered `宮崎駿` → `鈴木敏夫` with 31 shared works, subject links, years, and both people’s roles.
  - Shareable route smoke:
    - `/person/1040` loaded the `宮崎駿` person galaxy and sidebar.
    - `/path?from=1040&to=2215` loaded both endpoints and rendered direct collaboration/path evidence.
    - `/compare?from=1040&to=2215` loaded both endpoints in `双人比较` mode and rendered 31 direct shared works.
    - From `/person/1040`, the first collaborator `比较两人合作` action opened `/compare?from=1040&to=2215`.
  - Browser history smoke after route-state fix:
    - `/` loaded 21,006 people and 3,797 visible global edges with `全量星系`.
    - Search `宫崎骏` opened `/person/1040` with 94 people and 93 local edges.
    - Opening `/path`, then browser Back restored `/person/1040` with the 94-person local galaxy.
    - Browser Back again restored `/` with the 21,006-person global galaxy.
    - Opening `/compare` from the person-panel collaborator action, then browser Back restored `/person/1040`.
  - Console check returned no warnings or errors.
- Person credits endpoint:
  `/api/person/1040/credits?limit=3`
  returned three row-level credits with raw positions, normalized roles, tiers, weights, subject IDs, and Bangumi-ready subject names.
- Direct complete-edge path not present in visible graph:
  `/api/path/11706/21362?max_paths=3`
  returned degree 1 in about 0.66s via `curl`.
- Non-direct complete graph path:
  `/api/path/1040/11706?max_paths=3&max_depth=4`
  returned degree 2 in about 3.02s via `curl`.

## Pending Measurements

- Broader browser samples across multiple reloads and hardware states.
- Person-centered galaxy load time for several high-degree and low-degree people beyond `宮崎駿`.
- Interaction timing for drag/zoom/hover behavior inside Cosmos.
