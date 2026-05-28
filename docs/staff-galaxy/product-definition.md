# Staff Galaxy Product Definition

## One Sentence

以动画制作人员为星体，以共同参与作品为连线，探索动画业界中的合作关系、团队结构与职业轨迹。

## Product Position

Staff Galaxy 的核心价值是把 Bangumi Archive 中的 STAFF 事实记录投影成人物合作网络，让用户能探索：

- 这个人和谁合作过
- 两个人是否共同参与过作品
- 他们合作过几次，分别在什么职位
- 两人之间通过谁可以联系到（六度理论验证）
- 某个人最稳定的合作圈是谁
- 动画业界合作网络的大致星团结构

## Non-Goals

- 不推荐"下一部动画"
- 不把动画作品作为默认图节点
- 不爬 Bangumi 网页
- 不把全部 STAFF 直接两两投影后全量渲染
- 不预生成所有人物对详情文件

## Core User Journeys

### Journey 1: Explore the galaxy

```text
进入网站 → 看到人物总星系 → 缩放/平移浏览 → 悬停看人名 → 点击进入个人星系
```

### Journey 2: Search and focus

```text
搜索人名或 Bangumi ID → 定位并进入个人星系 → 查看合作者列表
→ 展开合作详情看共同作品和各自职位 → 点击邻居继续探索
```

### Journey 3: Path finding (六度理论)

```text
进入关系星图 → 选择起点人物 → 选择终点人物 → 探寻路径
→ 看到多条最短路径 → 悬停路径高亮 → 点击路径节点跳转
```

## Product Semantics

### Default Node

默认图中的节点只表示真实个人 (`person.type = 1`)。公司、组合、作品不作为默认节点。

### Default Edge

默认图中的边表示两位人物至少共同参与过一部动画作品。边通过稀疏化规则被选中进入默认可见图：
- `sharedWorksCount >= 2`，或
- 该边属于某端点最强的 top 10 邻居

### Evidence Layer

动画作品是人物关系的证据层，不出现在默认图中但可从侧栏查询：
- 共同作品名称、年份
- 双方各自的职位
- 首次和最近合作年份
- 合作评分（基于职位重要性的加权计算）

## Visual Direction

- 深色全屏星图（#0a0a0f 背景）
- 白色小圆点节点，高度数节点略带暖色
- 边为暖灰蓝→青色渐变，强度驱动透明度与宽度
- 节点大小反映可见加权度数（对数尺度）
- 悬停显示白环 + 浮空标签
- 选中显示金色环
- 设计参考：Obsidian Graph View

## Key Product Principle

完整数据要保留，但不能全部画出来。默认图是稀疏骨架，证据通过搜索和详情面板按需加载。
