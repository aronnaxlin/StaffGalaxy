# Graph Performance

Last updated: 2026-05-28 10:44 Asia/Shanghai

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
- Search terms: 253,609 terms across 83,565 real people (`name`: 83,565, `infobox`: 170,044).

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
| `dist/assets/index-DvZ06imf.css` | 28.89 KB | 5.87 KB |
| `dist/assets/index-D5oST6Ra.js` | 655.12 KB | 187.25 KB |

Vite warns that the main JavaScript chunk is over 500 KB. Cosmos.gl is expected to be the largest dependency; code splitting remains a pending optimization.

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

- Browser first render and interaction timing for global/l0/l1 graph levels.
- Search latency distribution for no-result cases and broader percentile samples.
- Person-centered galaxy load time for high-degree and low-degree people.
- Detail panel collaboration expansion timing.
- Console/runtime checks in the browser.
