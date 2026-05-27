# Direction Decisions

## Current Product Bet

Staff Galaxy 的核心不是“找动画”，而是“看动画制作人员之间的合作关系”。

因此 MVP 的第一性问题是：

```text
Bangumi Archive 的 STAFF 数据能否被稳定、可解释、可交互地投影成人物合作图？
```

如果这个问题成立，再谈更丰富的探索、路径、时间演化和推荐。

## Decisions Locked For MVP

### 1. Default Graph Nodes Are People Only

默认图只显示人物，不显示作品节点。

理由：

- 用户路径是从人开始探索合作网络。
- 作品作为证据层存在，不应和人物节点混在默认星系里。
- 二部图会改变视觉语义，让“人物总星系”变成“人物与作品混合网络”。

### 2. Anime Works Stay In The Evidence Layer

作品数据必须保留，但退到边的证据层。

任何人物关系都必须能回答：

- 共同参与了哪部作品
- 分别担任什么职位
- 首次和最近合作年份是什么

### 3. Do Not Render Full Staff Projection

不把一部作品的所有 STAFF 直接全量两两连边后渲染。

理由：

- 一部 80 人 STAFF 的作品会产生 3160 条人物边。
- C 层职位数量大，会制造大量弱连接。
- 全量投影既影响性能，也影响图的解释性。

### 4. Keep Full Evidence, Render Sparse Graph

核心策略：

```text
完整证据层保留全部可用 STAFF 事实
默认星图层只渲染被筛选出的稀疏强关系
```

这是产品与工程共同的约束。

### 5. Data Audit Before Frontend

现在最该先做数据审计，而不是 Mock Graph View。

原因：

- 默认图应该显示多少节点不知道。
- 骨架边应该保留多少不知道。
- Tier A、A+B、A+B+C 的规模差异不知道。
- 没有真实数字，前端设计很容易变成漂亮但不可落地的幻觉。

## Preferred MVP Stack

### Data Pipeline

- Python 3.12
- DuckDB
- Polars preferred, Pandas acceptable
- Markdown report output

### Frontend

- Vite
- React
- TypeScript
- Tailwind CSS
- Sigma.js
- Graphology

### Hosting Shape

第一版优先静态文件：

```text
DuckDB → exported JSON → static frontend
```

暂不引入后端服务，除非数据审计证明静态文件方案不可行。

## Main Risks

### Archive Format Risk

Bangumi Archive 文件名、字段、压缩格式可能与预期不一致。

处理方式：

- 审计脚本做文件探测。
- 错误信息必须指明缺少什么字段或文件。
- 保留原始职位文本，避免职位标准化失败导致数据丢失。

### Edge Explosion Risk

全量人物投影可能过大。

处理方式：

- 审计阶段先估算，不盲目物化。
- 分 Tier 测试。
- 分 pruning 策略测试。

### Visual Readability Risk

真实图可能因为高度中心化或职位噪声导致不可读。

处理方式：

- 先只用 Tier A 建核心骨架。
- 使用社区颜色，而非职位颜色。
- 节点大小和边权使用封顶后的对数尺度。

### Evidence Completeness Risk

Bangumi 记录可能不完整，不应把结果表达成绝对事实。

处理方式：

- 前端显示数据快照时间。
- 前端明确提示“基于当前 Bangumi Archive 快照，记录可能不完整”。

## Next Task Prompt

下一步可以把下面这段交给 coding agent：

```text
Implement the Bangumi Archive data audit pipeline for Staff Galaxy.

Use the specification in:
docs/staff-galaxy/data-audit-spec.md

Do not build the frontend yet.
Do not scrape Bangumi webpages.
Only process local archive files under data/raw/.

The deliverables are:
- data/processed/staff_galaxy.duckdb
- reports/data-audit.md

The report must compare Tier A, Tier A+B, and Tier A+B+C graph sizes and recommend the first visible graph export settings.
```

## Decision Pending Real Data

这些问题必须等 `reports/data-audit.md` 出来再定：

- 默认图用 Tier A 还是 Tier A+B。
- `sharedWorksCount` 默认阈值。
- top-K 邻居保留 `5`、`10`、`12` 还是 `20`。
- 初始页面是否加载所有可见边。
- 是否第一版就需要 community-level lazy loading。

