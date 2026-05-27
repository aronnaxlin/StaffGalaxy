# Data Audit Specification

## Purpose

Staff Galaxy 的第一步不是前端，而是数据规模审计。

原因：只有拿到真实 Bangumi Archive 快照的规模数字，才能决定默认星图是否能一次性加载核心人物图、默认骨架边保留多少、A/B/C 哪些职位层进入可见图。

## Audit Deliverable

实现一个本地数据审计流水线，输出：

```text
data/processed/staff_galaxy.duckdb
reports/data-audit.md
```

## Input Assumption

Bangumi Archive 文件放在：

```text
data/raw/
```

审计脚本应尽量鲁棒地探测文件名与格式；如果实际快照结构与预期不同，必须给出清晰错误信息。

Bangumi Archive 仓库本身只保存说明和 `aux/latest.json`。真实数据来自 release zip，例如：

```text
dump-YYYY-MM-DD.HHMMSSZ.zip
```

zip 内部目前包含：

```text
subject.jsonlines
person.jsonlines
character.jsonlines
episode.jsonlines
subject-relations.jsonlines
subject-persons.jsonlines
subject-characters.jsonlines
person-characters.jsonlines
person-relations.jsonlines
```

`subject-persons.jsonlines` 的 `position` 字段是数字职位常量，不是中文/日文职位文本。审计脚本必须读取 `bangumi/common` 的 `subject_staffs.yml`，将 position id 映射为职位元数据。

## Recommended Stack

- Python 3.12
- DuckDB
- Polars preferred, Pandas acceptable
- Rich optional, only for CLI readability

## Required Pipeline Steps

1. Detect local Bangumi Archive files under `data/raw/`.
2. Import subject records.
3. Import person records.
4. Import subject-person STAFF records.
5. Filter subject records to anime only: `subject.type = 2`.
6. Filter person records to real individuals only: `person.type = 1`.
7. Load Bangumi staff constants from `subject_staffs.yml`.
8. Normalize numeric staff positions into role keys, tiers, and weights.
9. Write DuckDB database to `data/processed/staff_galaxy.duckdb`.
10. Generate Markdown audit report at `reports/data-audit.md`.

## Required Report Sections

`reports/data-audit.md` must include:

- Snapshot metadata if available
- Number of anime subjects
- Number of real individual persons with anime credits
- Total anime staff credit count
- Top raw position ids by credit count, with mapped Chinese and English labels
- Normalized role counts
- Unknown or intentionally unmapped role count
- Candidate graph counts for Tier A only
- Candidate graph counts for Tier A + Tier B
- Candidate graph counts for Tier A + Tier B + Tier C
- Estimated edge explosion before pruning
- Filtered graph sizes under pruning strategies
- Recommendation for the first visible graph export settings

## Candidate Graph Counts

For each role layer:

```text
Tier A only
Tier A + Tier B
Tier A + Tier B + Tier C
```

Report:

- Number of participating persons
- Number of participating subjects
- Number of credits
- Estimated unpruned person-pair edges
- Number of unique candidate edges if feasible
- Warning if full materialization would be too large

## Pruning Strategy Tests

For each role layer, test:

- `sharedWorksCount >= 2`
- top 5 strongest neighbors per node
- top 10 strongest neighbors per node
- top 20 strongest neighbors per node

Report for each strategy:

- visible node count
- visible edge count
- max degree
- median degree
- p95 degree
- approximate JSON export size if possible

## Edge Explosion Estimate

For each subject:

```text
personCount * (personCount - 1) / 2
```

Sum across subjects to estimate raw pair contribution.

Do not blindly materialize the full all-role person-pair table if the estimate is too large.

## Collaboration Score

For a shared work:

```text
contribution = sqrt(roleWeightA * roleWeightB)
```

Initial role weights:

| Role | Weight |
| --- | ---: |
| director | 10 |
| assistant_director | 8 |
| series_composition | 8 |
| animation_producer | 8 |
| character_design | 7 |
| chief_animation_director | 7 |
| producer | 6 |
| music | 5 |
| storyboard | 4 |
| episode_director | 4 |
| script | 4 |
| animation_director | 3 |
| art_director | 3 |
| photography_director | 3 |
| sound_director | 3 |
| key_animation | 1 |
| second_key_animation | 1 |
| production_assistant | 1 |
| setting_production | 1 |

## Initial Position ID Mapping

The first audit implementation should start with this explicit anime position mapping from `subject_staffs.yml`:

| Position ID | Staff Label | Normalized Role | Tier | Weight |
| ---: | --- | --- | --- | ---: |
| 2 | 导演 | director | A | 10 |
| 74 | 总导演 | director | A | 10 |
| 72 | 副导演 | assistant_director | A | 8 |
| 10 | 系列构成 | series_composition | A | 8 |
| 8 | 人物设定 | character_design | A | 7 |
| 14 | 总作画监督 | chief_animation_director | A | 7 |
| 87 | 动画制片人 | animation_producer | A | 8 |
| 54 | 制片人 | producer | A | 6 |
| 6 | 音乐 | music | A | 5 |
| 4 | 分镜 | storyboard | B | 4 |
| 5 | 演出 | episode_director | B | 4 |
| 3 | 脚本 | script | B | 4 |
| 15 | 作画监督 | animation_director | B | 3 |
| 11 | 美术监督 | art_director | B | 3 |
| 17 | 摄影监督 | photography_director | B | 3 |
| 44 | 音响监督 | sound_director | B | 3 |
| 20 | 原画 | key_animation | C | 1 |
| 21 | 第二原画 | second_key_animation | C | 1 |
| 56 | 制作进行 | production_assistant | C | 1 |
| 84 | 设定制作 | setting_production | C | 1 |

Potential future additions to evaluate after the first report:

- `52` 执行制片人
- `58` 总制片人
- `59` 联合制片人
- `80` 监制
- `90` 作画监督助理
- `51` 补间动画

These should not be silently merged into the MVP role tiers without measuring their effect.

## Module Layout Proposal

```text
staff_galaxy/
├── __init__.py
├── archive_detect.py
├── duckdb_schema.py
├── ingest.py
├── roles.py
├── graph_audit.py
├── report.py
└── cli.py
```

Scripts:

```text
scripts/
└── audit_data.py
```

## CLI Shape

```bash
python scripts/audit_data.py \
  --raw-dir data/raw \
  --db data/processed/staff_galaxy.duckdb \
  --report reports/data-audit.md
```

## Engineering Requirements

- Modular Python files, not one enormous script.
- Typed functions where practical.
- Deterministic output ordering.
- Clear errors for missing archive files.
- Clear errors for missing `subject_staffs.yml`.
- No web scraping.
- No frontend work in this phase.
- No recommendation logic.
- Preserve raw positions even after normalization.
- Track unmapped roles for later mapping improvement.

## Acceptance Criteria

The audit phase is complete when:

- The database builds successfully from local archive files.
- The report contains real scale numbers.
- The report makes a concrete recommendation for default graph role layer and pruning settings.
- The next phase can choose thresholds from evidence rather than guessing.
