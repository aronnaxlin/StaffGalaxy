# Data Model And Architecture

## Architecture Summary

Staff Galaxy 使用两层数据模型：

| Layer | Content | Purpose |
| --- | --- | --- |
| 完整证据层 | 人物、作品、职位原始 STAFF 记录 | 精确查询两个人共同作品 |
| 默认星图层 | 筛选和稀疏化后的人物合作边 | 初始全局 Graph View |

MVP 应先用静态文件驱动前端，避免过早引入服务端复杂度。

```text
Bangumi Archive files
→ local audit and import pipeline
→ DuckDB fact database
→ visible graph export pipeline
→ static JSON files
→ React + Sigma.js graph explorer
```

## Raw Fact Model

### subjects

```sql
CREATE TABLE subjects (
  id INTEGER PRIMARY KEY,
  type INTEGER,
  name TEXT,
  name_cn TEXT,
  date TEXT,
  platform TEXT,
  score DOUBLE,
  rank INTEGER
);
```

MVP 只保留 `type = 2` 的动画条目进入 STAFF 关系分析。

### persons

```sql
CREATE TABLE persons (
  id INTEGER PRIMARY KEY,
  name TEXT,
  type INTEGER,
  career TEXT,
  summary TEXT
);
```

MVP 只保留 `type = 1` 的真实个人。

### credits

```sql
CREATE TABLE credits (
  subject_id INTEGER,
  person_id INTEGER,
  position_id INTEGER,
  position_cn TEXT,
  position_en TEXT,
  position_jp TEXT,
  normalized_role TEXT,
  role_tier TEXT,
  role_weight DOUBLE,
  appear_eps TEXT
);
```

`credits` 是最重要的事实表。所有人物关系必须能回溯到这里。

Bangumi Archive 当前快照中，`subject-persons.jsonlines` 的 `position` 是数字职位常量。实现中使用 `bangumi/common` 的 `subject_staffs.yml` 将其映射为中文、英文、日文职位标签，再归一化到 Staff Galaxy 的 role tier。

## Visible Graph Model

### visible_person_edges

```sql
CREATE TABLE visible_person_edges (
  source_person_id INTEGER,
  target_person_id INTEGER,
  shared_works_count INTEGER,
  collaboration_score DOUBLE,
  first_year INTEGER,
  last_year INTEGER,
  role_layer TEXT,
  top_neighbor_rank INTEGER,
  selection_reason TEXT
);
```

只保存默认星图或局部星团中值得显示的稀疏人物边。

当前 MVP 数据库实现先生成 Tier A 默认骨架边：

```text
sharedWorksCount >= 2 OR top 10 strongest neighbors per endpoint
```

2026-05-19 快照下，该规则生成 `113,943` 条可见边，覆盖 `11,571` 位人物。

### graph_nodes

```sql
CREATE TABLE graph_nodes (
  person_id INTEGER PRIMARY KEY,
  community_id INTEGER,
  x DOUBLE,
  y DOUBLE,
  visible_degree INTEGER,
  visible_weighted_degree DOUBLE,
  node_size DOUBLE,
  role_layer TEXT,
  layout_method TEXT
);
```

坐标必须离线计算并固定保存。前端首次打开不运行完整力导向布局。

当前数据库实现先为 Tier A 人物生成稳定的 `deterministic_spiral_v1` 坐标，作为导出和前端接线用的占位布局。正式视觉版本仍应替换为 ForceAtlas2 或 Leiden/ForceAtlas2 离线布局。

## Detail Views

数据库还提供几个查询视图，服务人物详情和边详情：

```sql
credit_details
person_role_counts
person_anime_stats
visible_edge_details
```

其中：

- `credit_details` 展开人物、作品、职位、tier，用于人物详情和双人共同作品查询。
- `person_role_counts` 统计某个人的职位分布。
- `person_anime_stats` 统计某个人动画 credit 数、参与作品数、A/B/C tier 分布、首次和最近年份。
- `visible_edge_details` 展开默认骨架边两端人物名和合作强度。

## Collaboration Edge Shape

前端展示层可以使用：

```ts
interface CollaborationEdge {
  sourcePersonId: number;
  targetPersonId: number;
  sharedWorksCount: number;
  visibleScore: number;
  firstCollaborationYear?: number;
  lastCollaborationYear?: number;
  topEvidence: Array<{
    subjectId: number;
    subjectName: string;
    year?: number;
    sourceRole: string;
    targetRole: string;
  }>;
}
```

默认 backbone 边可以更轻：

```ts
interface VisibleEdge {
  id: string;
  source: number;
  target: number;
  sharedWorksCount: number;
  collaborationScore: number;
  strongestRolePairs: Array<{
    sourceRole: string;
    targetRole: string;
    count: number;
  }>;
  sampleSubjects: Array<{
    id: number;
    name: string;
    year?: number;
  }>;
}
```

## Role Tiers

### Tier A: Core Global Graph Roles

用于默认全局骨架图：

- 监督 / 監督 / 导演 -> `director`
- 副监督 / 副監督 / 副导演 -> `assistant_director`
- 系列构成 / シリーズ構成 -> `series_composition`
- 角色设计 / キャラクターデザイン -> `character_design`
- 总作画监督 / 総作画監督 -> `chief_animation_director`
- 动画制片人 / アニメーションプロデューサー -> `animation_producer`
- 制片人 / プロデューサー -> `producer`
- 音乐 / 音楽 -> `music`

### Tier B: Extended Visible Roles

用于放大、局部社区或更宽松默认图实验：

- 分镜 / 絵コンテ -> `storyboard`
- 演出 -> `episode_director`
- 脚本 -> `script`
- 作画监督 / 作画監督 -> `animation_director`
- 美术监督 / 美術監督 -> `art_director`
- 摄影监督 / 撮影監督 -> `photography_director`
- 音响监督 / 音響監督 -> `sound_director`

### Tier C: Evidence Only For MVP

证据层保留，默认总星系不展开：

- 原画 -> `key_animation`
- 第二原画 -> `second_key_animation`
- 制作进行 / 制作進行 -> `production_assistant`
- 设定制作 / 設定制作 -> `setting_production`

## Collaboration Scoring

初始权重：

```ts
const ROLE_VISIBILITY_WEIGHT = {
  director: 10,
  assistant_director: 8,
  series_composition: 8,
  animation_producer: 8,
  character_design: 7,
  chief_animation_director: 7,
  producer: 6,
  music: 5,
  storyboard: 4,
  episode_director: 4,
  script: 4,
  animation_director: 3,
  art_director: 3,
  photography_director: 3,
  sound_director: 3,
  key_animation: 1,
  second_key_animation: 1,
  production_assistant: 1,
  setting_production: 1
};
```

单部作品中的一次合作贡献：

```text
contribution = sqrt(roleWeightA * roleWeightB)
```

总合作强度：

```text
collaborationScore =
  all shared work contributions
  + repeated collaboration bonus
```

## Default Edge Visibility

一条边进入默认图，应满足至少一个条件：

- 两人共同参与作品数量 `>= 2`
- `collaborationScore` 达到数据审计后确定的阈值
- 这条边属于某个节点最强的前 `K` 个邻居
- 用户主动搜索了其中一人或两人

`K` 的候选值：`8` 或 `12`。真实取值必须由数据审计报告决定。

## Static Data Export Shape

```text
public/data/
├── manifest.json
├── galaxy/
│   ├── nodes.json
│   ├── edges-backbone.json
│   └── communities.json
├── communities/
│   ├── community-001.json
│   ├── community-002.json
│   └── ...
├── persons/
│   ├── person-123.json
│   ├── person-456.json
│   └── ...
└── search/
    └── persons-index.json
```

### manifest.json

```json
{
  "snapshotDate": "2026-05-01",
  "nodeCount": 8200,
  "backboneEdgeCount": 18000,
  "communityCount": 74,
  "dataSource": "Bangumi Archive",
  "roleLayer": "core"
}
```

### galaxy/nodes.json

```json
[
  {
    "id": 123,
    "name": "人物名",
    "x": 0.183,
    "y": -0.442,
    "size": 3.6,
    "community": 12,
    "visibleDegree": 7
  }
]
```

### galaxy/edges-backbone.json

```json
[
  {
    "source": 123,
    "target": 456,
    "weight": 12.4,
    "sharedWorksCount": 3
  }
]
```

### persons/person-123.json

```json
{
  "id": 123,
  "name": "人物名",
  "roles": [
    {
      "role": "director",
      "count": 2
    }
  ],
  "credits": [
    {
      "subjectId": 1001,
      "subjectName": "作品 A",
      "year": 2022,
      "position": "监督"
    }
  ],
  "visibleNeighbors": [
    {
      "personId": 456,
      "sharedWorksCount": 3,
      "score": 12.4
    }
  ]
}
```

## Two Person Comparison

MVP 不生成 `pairs/123-456.json` 这类文件。

双人比较流程：

```text
load persons/person-A.json
load persons/person-B.json
intersect credits by subjectId
render shared works and both roles
```

如果证据层存在共同作品，但默认图中没有该边，前端临时添加一条高亮虚线边。
