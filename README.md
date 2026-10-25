# AnimeDNA

AnimeDNA 当前方向暂定为 **Staff Galaxy**：一个基于 Bangumi Archive 数据的动画制作人员合作星图。

当前仓库包含 Neo4j 知识图谱数据管线、FastAPI 后端和 React/Cosmos.gl 前端。

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

启动 Neo4j（Docker，Neo4j 5 Community + APOC + GDS）。先在项目根目录的 `.env`（已 git 忽略）里写好连接信息：

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<随便设一个>
```

```bash
docker compose up -d neo4j
```

Neo4j Browser：<http://localhost:7474>。数据目录在 `data/processed/neo4j/`。

准备本地数据：

```text
data/raw/
├── dump-YYYY-MM-DD.HHMMSSZ.zip
├── bangumi-archive/aux/latest.json
└── bangumi-common/subject_staffs.yml
```

完整重建知识图谱（会清空 Neo4j 里的现有数据）：

```bash
.venv/bin/python -m staff_galaxy.cli
```

输出：Neo4j 中的完整图谱，以及 `reports/data-audit.md`。

改了角色权重或布局算法后，只重建派生层（`COLLAB` 边、星系节点、布局、搜索词），不重新导入：

```bash
.venv/bin/python -m staff_galaxy.cli --derived-only
```

## 本地应用

安装前端依赖：

```bash
cd frontend
npm install
```

运行后端 API（需要 Neo4j 已启动）：

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

测试使用一个独立的、会被清空的 Neo4j 实例（端口 7688），不会动主图谱：

```bash
docker compose --profile test up -d neo4j-test
.venv/bin/python -m unittest -v tests.test_api_complete_graph
.venv/bin/python -m compileall staff_galaxy scripts tests
cd frontend && npm run build
git diff --check
```

前端默认通过 Vite 代理访问后端；后端通过 `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` 连接图谱（环境变量优先于 `.env`）。

前端配置：

```bash
VITE_BANGUMI_BASE_URL=https://bgm.tv
```

## API 快览

后端默认地址：`http://127.0.0.1:8000`

| Endpoint | 用途 |
|---|---|
| `GET /api/manifest` | 图谱地址、Archive 快照、星系计数 |
| `GET /api/graph/buffers` | 星系二进制几何（位置、大小、社区、边） |
| `GET /api/graph/meta` | 星系节点元数据（名字、度数） |
| `GET /api/person/{id}/galaxy` | 星系成员的骨干合作者（侧栏列表） |
| `GET /api/person/{id}/knowledge-graph` | 局部知识图谱：(人)—[职位]→(作品) 子图 |
| `GET /api/person/{id}/detail` | 人物摘要、常见职位、最近参与作品 |
| `GET /api/person/{id}/credits` | 完整动画职位履历，保留 raw role |
| `GET /api/search/persons?q=...` | ID / 原名 / 简中 / 繁中 / 别名 / 罗马字 / 模糊搜索 |
| `GET /api/collaboration/{a}/{b}` | 两人直接共同作品证据 |
| `GET /api/path/{a}/{b}` | 在完整 Person–Anime 图上的最短合作路径 |

## 数据语义

- 存储层是知识图谱：`(:Person)-[:CREDITED {职位, 档位, 权重}]->(:Anime)`，另有 `Character`、`Position`、`SearchTerm` 节点。
- 星系视图里的节点只有 Bangumi `person.type = 1` 的真实个人；作品是边背后的证据，不在星系中渲染。
- 星系边是预计算的 `COLLAB` 骨干：在二分图配置模型（BiCM）下统计显著的合作（FDR 0.05），并上最大生成森林保证不孤立任何人；比较和路径直接在完整 `CREDITED` 图上实时推导。
- 只分析 `subject.type = 2` 的动画作品。

更多阶段记录见 [Goal Progress](reports/goal-progress.md)，当前性能记录见 [Graph Performance](reports/graph-performance.md)。
