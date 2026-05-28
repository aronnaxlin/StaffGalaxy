# Goal Progress

Last updated: 2026-05-28 10:56 Asia/Shanghai

## Current State

- Branch: `codex/db-backed-renderer-research`.
- Local database: `data/processed/staff_galaxy.duckdb`.
- Current archive: `data/raw/dump-2026-05-19.210434Z.zip`.
- Backend: FastAPI live DuckDB API.
- Frontend: React 19 + TypeScript + Tailwind CSS 4 + Vite + Cosmos.gl.

## Verified This Turn

- Read required project and `karpathy-guidelines` instructions.
- Added lightweight frontend runtime instrumentation:
  - API responses now record URL, status, duration, and success in `window.__staffGalaxyMetrics`.
  - Cosmos graph readiness now records level, node count, total edges, visible edges, and edge cutoff.
  - Vite preview now proxies `/api` to the local FastAPI backend, enabling production-build runtime measurements without a separate reverse proxy.
- Measured production-preview runtime behavior and updated `reports/graph-performance.md`:
  - Global `/` reaches `cosmos-ready` in 824.4 ms with 21,006 nodes and 3,797 total edges.
  - `/person/1040` reaches person `cosmos-ready` in 185.9 ms with 94 nodes and 93 edges.
  - Expanding `宮崎駿` ↔ `鈴木敏夫` collaboration evidence took 189.7 ms through the preview browser proxy.
  - `/compare?from=1040&to=2215` reached direct collaboration evidence in 402.1 ms.
  - `/path?from=1040&to=11706` reached a rendered 2-degree path in 3,049.0 ms.
  - API timings for `global`/`l0`/`l1` graph endpoints and five-query search distribution samples are now recorded.
- Browser console check after production-preview runtime measurement returned no warnings or errors.
- Confirmed Python modules and tests compile: `.venv/bin/python -m compileall staff_galaxy scripts tests`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.

## Previously Verified

- Read required project and `karpathy-guidelines` instructions.
- Added first-class direct-compare routing:
  - `/compare?from={id}&to={id}` now preserves compare mode instead of rewriting to `/path`.
  - The Constellation sidebar labels direct compare mode as `双人比较` and keeps path mode as `关系星图`.
  - Person-panel collaborator rows now include a compact `比较两人合作` action that opens `/compare` with the current person and collaborator preselected.
- Fixed duplicate same-URL history writes during Constellation auto-query, so a compare action can return to the prior person route with one browser-back step.
- Browser smoke checked:
  - `/compare?from=1040&to=2215` loads in compare mode and renders 31 direct shared works for `宮崎駿` ↔ `鈴木敏夫`.
  - `/person/1040` → first collaborator `比较两人合作` opens `/compare?from=1040&to=2215`.
  - Browser history back from that compare route restores `/person/1040`.
  - Browser console check returned no warnings or errors.
- Confirmed backend regression tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed Python modules and tests compile: `.venv/bin/python -m compileall staff_galaxy scripts tests`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.
- Confirmed whitespace check passes: `git diff --check`.

- Read required project and `karpathy-guidelines` instructions.
- Added bounded fuzzy search:
  - Romanized/ASCII typo fallback uses DuckDB `damerau_levenshtein` over compact indexed terms.
  - CJK/kana fallback uses a bounded Unicode edit-distance pass over same-prefix, similar-length DB candidates, only after exact/alias/CJK-variant search has run.
  - Fuzzy results append after stronger exact/prefix/contains matches and are excluded from duplicate person IDs.
- Added backend regression coverage for romanized typo `Miyazki Hayao` and CJK typo `宫崎俊`.
- Verified real DB fuzzy behavior:
  - `Miyazki Hayao`, `Hayao Miyazki`, and `Hyao Miyazaki` return `1040` / `宮崎駿`.
  - `宫崎俊` and `鈴木敏雄` return plausible one-edit CJK candidates; the intended `宮崎駿` / `鈴木敏夫` records are in the top 3, but these inputs are naturally ambiguous.
- Confirmed backend regression tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.

- Read required project and `karpathy-guidelines` instructions.
- Added Archive-backed person display-name variants:
  - API responses now include `nameCn` from real Archive `简体中文名` infobox fields for graph nodes, person galaxies, search results, person detail/credits, collaboration details, and path people.
  - Added a localStorage-backed person name preference (`原名` / `简中`) using `staffGalaxy.personNameMode`.
  - Original names remain the default and fallback; no translations are invented.
  - Graph hover labels, person panel header/neighbors, search result rows/locked pills, constellation locked pills, path labels, and direct/path evidence role labels use the preference.
- Verified direct API calls:
  - Search `宫崎骏` returns `1040` with `name=宮崎駿`, `nameCn=宫崎骏`.
  - `person_detail(1040)` returns `nameCn=宫崎骏`.
  - `shortest_path(1040, 2215)` returns `nameCn=宫崎骏` and `nameCn=铃木敏夫` for the endpoints.
- Browser smoke checked person-name preference:
  - `/person/1040` toggles to `简中`, showing `宫崎骏` as primary and `宮崎駿` as secondary.
  - Neighbor labels switch to Archive-provided simplified names such as `铃木敏夫`, with original names shown as secondary when different.
  - `/path?from=1040&to=2215` shows simplified endpoint pills, path labels, and direct evidence role labels.
  - Browser console check reported no warnings or errors.
- Confirmed backend regression tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed Python modules and tests compile: `.venv/bin/python -m compileall staff_galaxy scripts tests`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.

- Read required project and `karpathy-guidelines` instructions.
- Added DB-backed data snapshot metadata:
  - New `data_snapshots` table records the current Bangumi Archive zip, Archive `created_at`, zip size, local build timestamp, and source URL.
  - Full rebuild now records the snapshot through `staff_galaxy.cli`.
  - Existing DBs can be backfilled with `scripts/migrate_data_snapshot.py`.
  - The current local DB now records `dump-2026-05-19.210434Z.zip`, created at `2026-05-19T21:04:35Z`, size `404,069,971` bytes.
- Exposed snapshot metadata through `/api/manifest`, `/api/person/{id}/detail`, `/api/person/{id}/credits`, and `/api/collaboration/{a}/{b}`.
- Added snapshot labels to the person panel and Constellation direct/path evidence UI.
- Added backend regression coverage for manifest, person detail, person credits, and collaboration source snapshots.
- Updated README and data-model docs with snapshot/search migration workflow.
- Verified direct API calls show the same snapshot for manifest, `宮崎駿` detail, and `宮崎駿` ↔ `鈴木敏夫` collaboration evidence.
- Browser smoke checked snapshot labels:
  - `/person/1040` shows `Bangumi Archive local DuckDB · dump-2026-05-19.210434Z.zip · 2026-05-19`.
  - `/path?from=1040&to=2215` shows the same snapshot in direct collaboration evidence.
  - Expanding the `宮崎駿` → `鈴木敏夫` path hop shows the same snapshot in hop evidence.
  - Browser console check reported no warnings or errors.
- Confirmed backend regression tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed Python modules and tests compile: `.venv/bin/python -m compileall staff_galaxy scripts tests`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.

- Read required project and `karpathy-guidelines` instructions.
- Verified the interrupted search-index migration did not leave a running process and the DuckDB file opens read-only.
- Confirmed the local DB now has `persons.infobox`, 93,579 non-empty person infobox rows, and 253,609 `person_search_terms` rows across 83,565 real people.
- Confirmed `person_search_terms` contains real Archive-derived aliases for `宮崎駿` (`1040`), including `Hayao Miyazaki`, `Miyazaki Hayao`, `みやざき はやお`, `宫崎骏`, and `照樹務`.
- Verified direct API search behavior against the real DB:
  - `Hayao Miyazaki`, `Miyazaki Hayao`, `照樹務`, `みやざき はやお`, `宫崎骏`, `宮崎駿`, and `1040` all return `1040` / `宮崎駿` as the first result.
- Browser smoke checked the search UI:
  - `Hayao Miyazaki` renders `宮崎駿 93 #1040`; selecting it opens `/person/1040`.
  - `照樹務` also renders `宮崎駿 93 #1040`.
  - Browser console check reported no warnings or errors.
- Confirmed backend regression tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed Python modules and tests compile: `.venv/bin/python -m compileall staff_galaxy scripts tests`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.

- Read required project and `karpathy-guidelines` instructions.
- Fixed route/history graph-state divergence:
  - Route changes are now the single owner of graph loading; click/search/back handlers only update URL route state.
  - Removed the stale in-place `swapGraph` path from the Cosmos renderer contract.
  - Browser back from `/path` to `/person/1040` now restores the 94-person `宮崎駿` local galaxy.
  - Browser back again to `/` now restores the 21,006-person global galaxy and `全量星系` label.
- Restarted Vite after confirming the browser was serving a stale transformed module, then repeated the smoke path against fresh source.
- Confirmed backend regression tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed Python modules and tests compile: `.venv/bin/python -m compileall staff_galaxy scripts tests`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.

- Read required project and `karpathy-guidelines` instructions.
- Added lightweight SPA route state for shareable views:
  - `/person/{id}` initializes the person-centered galaxy and opens the person detail panel.
  - `/path?from={id}&to={id}` initializes Constellation view, locks both search pills, and runs the path/direct-comparison query.
  - Opening a person or path updates `history.pushState` without adding a router dependency.
- Browser smoke checked:
  - `http://127.0.0.1:5173/person/1040` loads `宮崎駿`, 94-person local galaxy, and sidebar summary.
  - `http://127.0.0.1:5173/path?from=1040&to=2215` loads both endpoints and renders direct evidence/path for `宮崎駿` ↔ `鈴木敏夫`.
  - Browser console check reported no warnings or errors.
- Confirmed backend regression tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.

- Read required project and `karpathy-guidelines` instructions.
- Added `raw_position` storage to the `credits` schema and ingest path.
- Added an in-place schema guard for older local DuckDB files; the current local DB now has `credits.raw_position`.
- Added `GET /api/person/{person_id}/credits`:
  - Returns row-level anime credit history with subject names, years, Bangumi IDs, position IDs, raw positions, normalized roles, tiers, weights, and `appear_eps`.
  - Supports bounded `limit` and `offset` query parameters.
- Added frontend loading/caching and an expandable `完整履历` section in `NodePanel`.
- Browser/API smoke checked `宮崎駿` (`1040`):
  - `/api/person/1040/credits?limit=3` returns raw/normalized/tiered role rows for `君たちはどう生きるか`.
  - Sidebar expands to a grouped 190-credit history with linked subjects and role chips.
  - Browser console check reported no warnings or errors.
- Added backend regression coverage for raw-position person credits.
- Confirmed backend regression tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed Python modules and tests compile: `.venv/bin/python -m compileall staff_galaxy scripts tests`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.

- Read required project and `karpathy-guidelines` instructions.
- Added expandable per-hop path evidence in `ConstellationView`:
  - Each shortest-path hop now has an `展开证据` control in the path legend.
  - Expanded evidence shows shared-work count, score, linked Bangumi subjects, years, and both people’s roles.
  - Evidence uses the existing complete collaboration query, so it can include relationships hidden from the renderer layer.
- Fixed collaboration-detail cache orientation so a cached unordered pair is returned with roles aligned to the requested person A/B order.
- Browser smoke checked `宮崎駿` (`1040`) ↔ `鈴木敏夫` (`2215`):
  - Direct comparison still renders 31 shared works.
  - Path legend shows `展开证据 · 宮崎駿→鈴木敏夫`.
  - Expanding the hop renders linked subject evidence and role lines for both people.
  - Browser console check reported no warnings or errors.
- Confirmed backend regression tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.

- Read required project and `karpathy-guidelines` instructions.
- Added `GET /api/person/{person_id}/detail` for person sidebar summaries:
  - Person identity, career JSON, and summary text.
  - Anime credit/subject totals, tier counts, and first/latest credit years.
  - Top role counts from `person_role_counts`.
  - Recent anime credits with subject names, years, roles, and Bangumi subject IDs.
- Added frontend detail loading/caching and rendered the new summary in `NodePanel`.
- Added backend regression coverage for the person detail response.
- Fixed the new endpoint defaults so direct unit-test calls and FastAPI requests both pass plain integer limits.
- Browser smoke checked `宮崎駿` from a simplified-CJK search:
  - Sidebar shows 79 anime, 190 position records, 1963–2023 year range, common roles, recent works, and source label.
  - Recent works link to Bangumi subject pages.
  - Browser console check reported no warnings or errors.
- Confirmed backend tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed Python modules and tests compile: `.venv/bin/python -m compileall staff_galaxy scripts tests`.
- Confirmed frontend production build passes: `npm run build`; Vite still warns that the main JS chunk exceeds 500 KB.

- Read required project and `karpathy-guidelines` instructions.
- Researched `bangumi.tv`, `bgm.tv`, `chii.in`, and a Bangumi person page for broad visual direction.
- Added `docs/DESIGN.md` with product tone, color tokens, typography, layout, component guidance, link policy, loading/empty/error states, and implementation notes.
- Added the design system document to the README reading order.

- Read required project and `karpathy-guidelines` instructions.
- Added a compact direct-collaboration comparison section to `ConstellationView`.
- The comparison section now:
  - Fetches direct evidence only when the complete-graph shortest path is degree 1.
  - Shows shared-work count, first/latest years, score, per-person roles, and Bangumi subject links for direct collaborators.
  - Shows an explicit “no direct collaboration evidence” hint when the shortest path is degree 2+.
  - Avoids issuing a failing collaboration request for non-direct pairs, keeping the browser console clean.
- Browser smoke checked:
  - `宮崎駿` (`1040`) ↔ `鈴木敏夫` (`2215`) shows direct collaboration evidence, 31 works, and subject links.
  - `宮崎駿` (`1040`) ↔ `飯飼一幸` (`11706`) shows no direct evidence and a 2-degree path.
  - Browser console check reported no warnings or errors after both comparison states.
- Confirmed frontend production build passes: `npm run build`.

- Read required project and `karpathy-guidelines` instructions.
- Added configurable Bangumi URL helpers in `frontend/src/data/links.ts`.
- Added `VITE_BANGUMI_BASE_URL` to `.env.example`.
- Added Bangumi person links in search result rows, locked comparison/search pills, constellation path labels, and the person detail footer.
- Added Bangumi subject links in expanded collaboration work cards.
- Added a localStorage-backed subject title display preference (`原名` / `中文`) for shared-work evidence cards.
- Browser smoke checked:
  - Search for `宫崎骏` shows `宮崎駿` with a `https://bgm.tv/person/1040` result link.
  - Opening `宮崎駿` detail and expanding `鈴木敏夫` collaboration shows subject links such as `https://bgm.tv/subject/228715`.
  - Switching the work-title preference to `中文` updates visible work titles and persists `staffGalaxy.subjectNameMode=cn`.
  - Constellation path labels render Bangumi person links for both endpoints.
  - Browser console check reported no warnings or errors.
- Confirmed frontend production build passes: `npm run build`.

- Read required project and `karpathy-guidelines` instructions.
- Added backend regression tests in `tests/test_api_complete_graph.py`:
  - Complete low-tier collaboration edges are queryable even when absent from `visible_person_edges`.
  - Shortest paths use `person_collaboration_edges`, including a path that depends on a hidden low-tier edge.
  - Numeric ID search and simplified-CJK variant search resolve expected people.
- Confirmed backend tests pass: `.venv/bin/python -m unittest -v tests.test_api_complete_graph`.
- Confirmed Python modules and tests compile: `.venv/bin/python -m compileall staff_galaxy scripts tests`.
- Confirmed frontend production build passes: `npm run build`.

- Read required project and `karpathy-guidelines` instructions.
- Confirmed frontend production build passes: `npm run build`.
- Confirmed Python modules compile: `python3 -m compileall staff_galaxy scripts`.
- Backed up DuckDB before derived-table migration:
  `data/processed/staff_galaxy.duckdb.bak-20260527-202450`.
- Materialized complete staff collaboration edges separately from visible graph edges:
  - `person_collaboration_edges`: 26,017,438 complete staff edges.
  - `visible_person_edges`: 518,581 sparse renderer edges.
  - `graph_nodes`: 21,006 people.
- Verified a direct collaboration missing from the visible renderer layer still resolves through the complete graph:
  - Pair: 飯飼一幸 (`11706`) and 小澤和則 (`21362`).
  - Complete collaboration: 202 shared works, score 814.79, `selectionReason=all_staff`.
  - Path endpoint: degree 1, one direct path.
- Verified a non-direct path on the complete graph:
  - Pair: 宮崎駿 (`1040`) and 飯飼一幸 (`11706`).
  - Result: degree 2, three shortest paths returned with `max_paths=3`.

## Requirement Coverage

- Data/schema: in progress. Core Bangumi Archive import exists; complete staff collaboration edge table now exists; visible graph remains a separate display layer; staff credits now include `raw_position` alongside normalized role metadata; `data_snapshots` records the current Archive source for evidence traceability.
- Search: in progress. Unified person search supports numeric ID, CJK variant expansion, Archive infobox aliases, kana, romanized names, and bounded fuzzy typo fallback through a DB-backed `person_search_terms` table with focused backend regression coverage and real-DB timing samples. Broader ranking/percentile tuning remains.
- Global graph: in progress. Cosmos.gl renderer consumes sparse `visible_person_edges`; complete evidence is preserved in DuckDB.
- Person graph/detail: in progress. Person-centered galaxy, sidebar summary stats/recent works, expandable complete credit history, and expandable collaboration detail exist.
- Two-person comparison: in progress. Constellation view now shows direct-collaboration evidence for degree-1 pairs and an explicit no-direct hint for degree-2+ pairs; `/compare?from=...&to=...` is shareable and person-panel collaborator rows can open it directly.
- Path: in progress. Backend now uses `person_collaboration_edges`, not `visible_person_edges`; frontend constellation view shows shortest paths and expandable per-hop evidence, and path URLs can be shared.
- Information panel/external links: in progress. Search results, selected search pills, person detail footer, shared-work cards, and constellation path labels now expose Bangumi links; person/detail/collaboration evidence surfaces now include snapshot metadata; subject display preference and person display-name preference exist with localStorage-backed toggles. Traditional-name mode remains pending because no verified source field has been wired yet.
- UI/design: in progress. Obsidian-like graph style exists, and `docs/DESIGN.md` now records tokens, layout rules, component states, and Bangumi-inspired constraints; implementation still needs further token extraction.
- Tests/performance: partial. Build/compile/API smoke checks pass, backend regression tests cover complete-vs-visible graph separation, path, collaboration detail, person detail, person credits/raw roles, and basic search. Browser smoke checks cover the link/preference/detail/path-evidence/credit-history/shareable-route surfaces, and production-preview runtime metrics now cover global graph, person graph, compare, path, collaboration expansion, graph endpoint payload timing, and search distribution samples.
- Routing/history: in progress. Shareable person/path/compare URLs exist and the known browser back divergence between `/path`, `/person/{id}`, and `/` is fixed.
- Deployment/docs: partial. `.env.example`, `.gitignore`, and README setup/import/test notes improved; deployment remains intentionally local-only.

## Next Best Work

- Add richer architecture docs for `person_collaboration_edges`, `/api/person/{id}/detail`, local startup, and rebuild/migration workflow.
- Extract repeated UI values into shared tokens once the prototype stabilizes.
- Add traditional-name handling if a verified Archive field is available.
- Broaden browser runtime measurements across repeated reloads, more people, and drag/zoom/hover interactions.
