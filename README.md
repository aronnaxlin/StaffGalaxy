# AnimeDNA

AnimeDNA 当前方向暂定为 **Staff Galaxy**：一个基于 Bangumi Archive 数据的动画制作人员合作星图。

当前仓库重点是确定产品定义、数据模型和实现路线，暂时不先做前端。

建议阅读顺序：

- [产品定义](docs/staff-galaxy/product-definition.md)
- [数据模型与架构](docs/staff-galaxy/data-model-and-architecture.md)
- [数据审计规格](docs/staff-galaxy/data-audit-spec.md)
- [实现路线图](docs/staff-galaxy/implementation-roadmap.md)
- [方向决策记录](docs/staff-galaxy/direction-decisions.md)
- [MVP 验收标准](docs/staff-galaxy/mvp-acceptance.md)

## 数据审计

准备本地数据：

```text
data/raw/
├── dump-YYYY-MM-DD.HHMMSSZ.zip
├── bangumi-archive/aux/latest.json
└── bangumi-common/subject_staffs.yml
```

运行审计：

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python scripts/audit_data.py
```

输出：

```text
data/processed/staff_galaxy.duckdb
reports/data-audit.md
```
