# MVP Acceptance Criteria

## Product Acceptance

- [ ] 进入页面默认看到人物总星系。
- [ ] 默认图中没有动画作品节点。
- [ ] 所有可见节点都对应 Bangumi 中的真实个人。
- [ ] 默认边表示共同参与动画作品。
- [ ] 默认边可以展开查看作品证据。
- [ ] 可以搜索并定位一个人。
- [ ] 可以输入两个人进行比较。
- [ ] 能显示两人共同参与过哪些动画。
- [ ] 能显示双方在共同作品中的职位。
- [ ] 隐藏于默认图的弱关系仍然可以通过搜索查出来。
- [ ] 全局图采用固定布局，不在首次加载时实时乱动。
- [ ] 有数据快照时间。
- [ ] 有“Bangumi 记录可能不完整”的说明。

## Data Acceptance

- [ ] 本地 Bangumi Archive 文件能被检测并导入。
- [ ] `subjects` 只保留动画条目用于 STAFF 图分析。
- [ ] `persons` 只保留真实个人用于默认图。
- [ ] `credits` 保留原始职位文本。
- [ ] 职位标准化模块能输出 role key、tier、weight。
- [ ] 未映射职位会进入报告，而不是被静默丢弃。
- [ ] 数据审计报告包含 Tier A、A+B、A+B+C 的规模对比。
- [ ] 默认图阈值来自真实审计数字。

## Graph Semantics Acceptance

- [ ] 节点颜色由社区决定，不由职位决定。
- [ ] 节点大小反映可见合作强度或可见连接数。
- [ ] 搜索人物有明显描边和常显标签。
- [ ] 对比人物有第二种选中状态。
- [ ] 默认边稀疏，不渲染全量两两 STAFF 边。
- [ ] 证据层完整保留 C 层职位关系。
- [ ] 双人比较能发现默认图中不可见的共同作品。

## Frontend Acceptance

- [ ] 初始加载使用固定坐标。
- [ ] 初始标签稀疏。
- [ ] 悬停节点显示名称并高亮邻居。
- [ ] 点击节点打开详情侧栏。
- [ ] 点击边打开合作证据。
- [ ] 搜索结果能平滑定位到节点。
- [ ] 双人比较能同时高亮两人。
- [ ] 如果两人有证据层关系但无默认边，前端临时显示高亮虚线边。
- [ ] 底部预留职位层、时间范围、边强度筛选。

## Performance Acceptance

- [ ] 初始页面不执行完整大图力导向布局。
- [ ] 初始页面不加载所有 person detail 文件。
- [ ] 初始页面不加载所有原始 credits。
- [ ] 大图渲染不会因为几十万弱边而不可交互。
- [ ] 后续性能优化能统计 JSON 体积、解析时间、渲染时间、可见节点数、可见边数。

## First Engineering Task

下一步唯一建议任务：

```text
Implement the Bangumi Archive data audit pipeline described in
docs/staff-galaxy/data-audit-spec.md.
```

在看到 `reports/data-audit.md` 之前，不建议开始真实 Graph View 或首页设计。

