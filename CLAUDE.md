# Claude Code Instructions

Read [AGENTS.md](AGENTS.md) before working on this project.

## Quick start

```bash
# Backend
.venv/bin/uvicorn staff_galaxy.api:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

## Project at a glance

- **Product**: Anime staff collaboration graph (nodes=people, edges=shared anime credits)
- **Backend**: FastAPI + DuckDB, port 8000
- **Frontend**: React 19 + TypeScript + Tailwind CSS 4 + Vite + Cosmos.gl, port 5173
- **Database**: `data/processed/staff_galaxy.duckdb` (git-ignored, built from Bangumi Archive)
- **Data source**: [Bangumi Archive](https://github.com/bangumi/Archive) dump zips

## Key files

| File | Role |
|---|---|
| `staff_galaxy/api.py` | All API endpoints |
| `staff_galaxy/roles.py` | Position tier/weight definitions (S/A/B/C/D/E/F, 163 positions) |
| `staff_galaxy/visible_edges.py` | Graph edge builder |
| `staff_galaxy/graph_nodes.py` | Graph node position/size builder |
| `staff_galaxy/database.py` | Schema, views, indexes |
| `frontend/src/components/CosmosGalaxyView.tsx` | WebGL galaxy renderer |
| `frontend/src/components/ConstellationView.tsx` | Path-finding SVG view |
| `frontend/src/components/NodePanel.tsx` | Person detail sidebar |
| `frontend/src/components/SearchBar.tsx` | Unified search with CJK variant support |
| `frontend/src/data/loader.ts` | API client functions |
| `frontend/src/App.tsx` | Root component, view routing |

## Active branch

Check `git branch --show-current`. Current work is on `codex/db-backed-renderer-research`.
