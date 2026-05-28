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

准备本地数据：

```text
data/raw/
├── dump-YYYY-MM-DD.HHMMSSZ.zip
├── bangumi-archive/aux/latest.json
└── bangumi-common/subject_staffs.yml
```

完整重建数据库：

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
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

运行 DuckDB 后端 API：

```bash
.venv/bin/uvicorn staff_galaxy.api:app --reload --host 127.0.0.1 --port 8000
```

另开一个终端运行前端：

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

## 验证

```bash
.venv/bin/python -m unittest -v tests.test_api_complete_graph
.venv/bin/python -m compileall staff_galaxy scripts tests
cd frontend && npm run build
```

前端默认通过 Vite 代理访问后端；后端数据库路径可用环境变量覆盖：

```bash
STAFF_GALAXY_DB=data/processed/staff_galaxy.duckdb
```

更多阶段记录见 [Goal Progress](reports/goal-progress.md)，当前性能记录见 [Graph Performance](reports/graph-performance.md)。
