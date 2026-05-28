# AnimeDNA

AnimeDNA 当前方向暂定为 **Staff Galaxy**：一个基于 Bangumi Archive 数据的动画制作人员合作星图。

当前仓库已经包含可运行的 DuckDB 数据管线、FastAPI 后端和 React/Cosmos.gl 前端。

建议阅读顺序：

- [产品定义](docs/staff-galaxy/product-definition.md)
- [设计系统](docs/DESIGN.md)
- [数据模型与架构](docs/staff-galaxy/data-model-and-architecture.md)
- [数据审计规格](docs/staff-galaxy/data-audit-spec.md)
- [实现路线图](docs/staff-galaxy/implementation-roadmap.md)
- [方向决策记录](docs/staff-galaxy/direction-decisions.md)
- [MVP 验收标准](docs/staff-galaxy/mvp-acceptance.md)

## 数据与导入

安装 Python 包：

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

准备本地数据：

```text
data/raw/
├── dump-YYYY-MM-DD.HHMMSSZ.zip
├── bangumi-archive/aux/latest.json
└── bangumi-common/subject_staffs.yml
```

完整重建数据库：

```bash
.venv/bin/python -m staff_galaxy.cli
```

输出：

```text
data/processed/staff_galaxy.duckdb
reports/data-audit.md
```

只更新角色权重并重建派生边/节点：

```bash
.venv/bin/python scripts/migrate_role_weights.py
```

只为已有本地数据库补齐搜索索引或数据快照元数据：

```bash
.venv/bin/python scripts/migrate_search_index.py
.venv/bin/python scripts/migrate_data_snapshot.py
```

## 本地应用

安装前端依赖：

```bash
cd frontend
npm install
```

运行 DuckDB 后端 API：

```bash
.venv/bin/uvicorn staff_galaxy.api:app --reload --host 127.0.0.1 --port 8000
```

另开一个终端运行前端：

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

打开：

```text
http://127.0.0.1:5173/
```

常用分享路由：

```text
/?level=l0
/?level=l1
/person/1040
/compare?from=1040&to=2215
/path?from=1040&to=11706
```

生产构建预览和性能测量：

```bash
cd frontend
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

Vite dev 和 preview 都会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 验证

```bash
.venv/bin/python -m unittest -v tests.test_api_complete_graph
.venv/bin/python -m compileall staff_galaxy scripts tests
cd frontend && npm run build
git diff --check
```

前端默认通过 Vite 代理访问后端；后端数据库路径可用环境变量覆盖：

```bash
STAFF_GALAXY_DB=data/processed/staff_galaxy.duckdb
```

前端配置：

```bash
VITE_BANGUMI_BASE_URL=https://bgm.tv
```

## API 快览

后端默认地址：`http://127.0.0.1:8000`

| Endpoint | 用途 |
|---|---|
| `GET /api/manifest` | 数据库路径、Archive 快照、图层计数 |
| `GET /api/graph/{level}/nodes` | `global` / `l0` / `l1` 图节点 |
| `GET /api/graph/{level}/edges` | 稀疏渲染边 |
| `GET /api/person/{id}/galaxy` | 个人中心星系 |
| `GET /api/person/{id}/detail` | 人物摘要、常见职位、最近参与作品 |
| `GET /api/person/{id}/credits` | 完整动画职位履历，保留 raw role |
| `GET /api/search/persons?q=...` | ID / 原名 / 简中 / 别名 / 罗马字 / 模糊搜索 |
| `GET /api/collaboration/{a}/{b}` | 两人直接共同作品证据 |
| `GET /api/path/{a}/{b}` | 基于完整合作图的最短路径 |

## 数据语义

- 节点是 Bangumi `person.type = 1` 的真实个人。
- 边表示两人参与过同一部动画的 staff credit。
- 动画作品是边的证据，不是默认图节点。
- 默认渲染使用稀疏 `visible_person_edges`；比较和路径使用完整 `person_collaboration_edges`。
- 只分析 `subject.type = 2` 的动画作品。

更多阶段记录见 [Goal Progress](reports/goal-progress.md)，当前性能记录见 [Graph Performance](reports/graph-performance.md)。
