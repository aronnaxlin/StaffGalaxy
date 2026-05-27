# Staff Galaxy Agent Guide

## Project Summary

Staff Galaxy is an anime staff collaboration graph based on Bangumi Archive.

Core product semantics:

- Default graph nodes are people.
- Default graph edges represent anime collaboration evidence.
- Anime works are not default graph nodes; they are evidence behind person-person relationships.
- Global graph should stay sparse and readable.
- Person detail and two-person comparison should be as complete as possible.

## Current Data Decision

Only `subject.type = 2` anime is in scope for the MVP.

Person handling:

- Default semantic nodes are Bangumi `person.type = 1`.
- Companies and groups are not default graph nodes.
- Some Bangumi `type = 1` records are actually companies/institutions; noisy roles such as `製作` are kept out of the default graph.

Role layers:

- `Tier A`: default global backbone candidates. Core creators, original creators/planning, main directors, core producers.
- `Tier B`: local expansion and prominent detail. Department leads, core episode/storyboard/script/direction roles, important producer/director variants.
- `Tier C`: normal person detail. Execution roles and useful evidence such as key animation, songs, photography, sound effects, settings, design support.
- `Tier D`: load-more/full-history detail. Assistance, cooperation, long-tail, very noisy, or entity-like roles.
- `CAST`: voice/cast layer from `person-characters.jsonlines`. Keep separate from staff tiers.

Default global graph:

```text
Tier A
sharedWorksCount >= 2 OR top 10 strongest neighbors per endpoint
```

Current generated database:

```text
data/processed/staff_galaxy.duckdb
```

Generated reports:

```text
reports/data-audit.md
reports/archive-feasibility.md
reports/position-role-audit.md
```

## Important Database Objects

Core tables:

- `subjects`
- `persons`
- `characters`
- `staff_positions`
- `credits`
- `person_characters`
- `visible_person_edges`
- `graph_nodes`

Useful views:

- `credit_details`
- `cast_details`
- `anime_participation_details`
- `person_role_counts`
- `person_anime_stats`
- `visible_edge_details`

Frontend and export code should prefer these views over reimplementing joins.

## Frontend Direction

The next frontend phase should create a graph exploration UI, not a marketing page.

Recommended stack:

- Vite
- React
- TypeScript
- Tailwind CSS
- Sigma.js
- Graphology

Expected first frontend goal:

- Load static JSON exported from DuckDB.
- Render a dark full-screen person galaxy.
- Show sparse labels globally.
- Search one person.
- Compare two people.
- Click person to show detail.
- Click edge to show evidence.
- If two people share evidence but no default edge exists, render a temporary highlighted/dashed edge.

Do not introduce:

- Anime recommendation features.
- Anime as default graph nodes.
- Browser-side full graph layout on first load.
- Full A+B+C+D edge rendering in the global view.

## Data Export Expectations

Next likely backend/data task is exporting:

```text
public/data/
├── manifest.json
├── galaxy/nodes.json
├── galaxy/edges-backbone.json
├── galaxy/communities.json
├── persons/person-[id].json
└── search/persons-index.json
```

Export semantics:

- `galaxy/nodes.json` should come from `graph_nodes`.
- `galaxy/edges-backbone.json` should come from `visible_person_edges`.
- Person detail files should include Tier A/B/C/CAST first and Tier D behind load-more/full-history affordances.
- Two-person comparison should use `anime_participation_details`, not only `credit_details`.

## Commands

Set up:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Rebuild database and reports:

```bash
.venv/bin/python scripts/audit_data.py
```

Compile check:

```bash
.venv/bin/python -m py_compile staff_galaxy/*.py scripts/audit_data.py
```

## Local Data Notes

Raw and processed data are ignored by git:

```text
data/raw/
data/processed/
```

Expected local raw inputs:

```text
data/raw/dump-*.zip
data/raw/bangumi-archive/aux/latest.json
data/raw/bangumi-common/subject_staffs.yml
```

## Collaboration Rules

- Keep changes scoped.
- Do not rewrite data semantics without updating this file and the relevant report/spec docs.
- Preserve full evidence even when hiding relationships from the default graph.
- Treat default graph visibility as a performance/readability choice, not as truth.
- Prefer explicit, verifiable SQL checks after data changes.

