# 星雲圖邊渲染性能：現狀評估與重構方案

Last updated: 2026-07-18（v4：Phase 1/2/3 已實施並用真實數據驗證）
Status: **Phase 1/2/3 已完成**（cosmos.gl v3、二進制傳輸、Leiden 分層佈局、三檔合併）；Phase 4/5 仍為提案

> **Phase 2/3 實施記錄（2026-07-18）：** `/api/graph/{level}/nodes|edges` 已刪除，替換為
> `GET /api/graph/buffers`（單一分段 buffer，7.8MB 裸 / 1.84MB gzip）+
> `GET /api/graph/meta`（labels.json 對應物，566KB gzip）；快照+幾何指紋做
> ETag/immutable 緩存。`graph_nodes.community_id` 已由 Leiden 填上（481 社群，
> `hier_leiden_fr_v1`），簇間 FR 之後加了一輪圓形打包（circle packing）防止
> 大簇質心重疊成亮斑；前端按 `community` 段做低飽和度色相偏移。global/l0/l1
> 三檔 UI 已刪除，替換為最小度數/邊數預算兩個客戶端滑桿。實測與已知限制見
> `reports/graph-performance.md`「Phase 2+3」一節。

目標：把星雲圖的邊（關係）渲染體驗極度逼近 Obsidian Graph View —— 全量邊常駐可見、60fps 平移縮放、懸停即時高亮鄰居、標籤隨縮放淡入 —— 而不是像現在這樣把邊砍到只剩零頭來自保。

> **Phase 1 實施記錄（2026-07-06）：** 已升級 cosmos.gl v2.6.4→3.1.0、懸停高亮改
> O(度數)、邊 LOD 改零拷貝前綴切片、global 層 `min_shared` 12→2，並用
> `dump-2026-06-30` 真實快照（21,383 節點 / 529,310 邊）端到端驗證：`min_shared>=2`
> 解鎖 372,661 條邊（舊 floor 只有 3,901 條）；global 默認縮放層級渲染
> 60,000/372,661 條邊，生產構建下 Cosmos 設備就緒約 3.06 秒（其中 ~3.0 秒是
> `/api/graph/global/edges` 55MB JSON 的下載+解析+graphology 構建，Cosmos 自身
> 只佔 ~50ms）——這正是 Phase 2 二進制傳輸要解決的問題，現在有真實數字支撐。
> 詳見 `AGENTS.md`「Performance characteristics」一節。

---

## 1. 現狀評估

### 1.1 數據規模（來自 `reports/graph-performance.md`，2026-05-28 快照）

| 層 | 節點 | 邊 | 邊 JSON 體積 |
|---|---:|---:|---:|
| global | 21,006 | 3,797（`min_shared=12`） | 0.59 MB |
| l0 | 1,477 | 134,931 | 19.44 MB |
| l1 | 4,422 | 119,441 | 17.72 MB |
| `visible_person_edges` 全量 | 21,006 | 518,581 | —（從未整體下發） |
| `person_collaboration_edges` 完整圖 | ~83K | 26,017,438 | —（僅服務端查詢） |

### 1.2 當前渲染數據流

```
DuckDB → FastAPI（JSON，數字轉文本）
  → fetch + JSON.parse（l0 邊 19.4MB）
  → 逐條 map 成 JS 對象（loader.ts）
  → graphology Graph（addNode/addEdgeWithKey，每條邊一個屬性對象）
  → buildCosmosPayload：再遍歷 graphology 轉回 Float32Array
  → Cosmos.gl 2.6.4（enableSimulation: false，預計算螺旋座標）
```

每次縮放結束（`onZoomEnd`）和**每次懸停/移出節點**（`applyHoverEdgeFocus`），
`buildEdgeArrays` 都對全部 `edgeRecords` 做一次 O(E) 的 filter + 重新分配
3 個 Float32Array + 整體重新上傳 GPU。

### 1.3 診斷結論：卡的不是 GPU，是喂數據的方式

按嚴重程度排序：

1. **邊是被政策砍掉的，不是被渲染掉的。** global 視圖 `min_shared=12` 只放行
   3,797 / 518,581 條邊（0.7%）；放大後 LOD 閾值升到 40，只剩 144 條。
   「邊不堪用」的直接原因是：管線撐不住，於是防禦性地把邊過濾到近乎沒有。
   Obsidian 的做法相反 —— 全量邊常駐，用透明度和距離做視覺 LOD。

2. **佈局沒有結構，導致邊「不能多」。** `deterministic_spiral_v1` 按加權度排名
   擺螺旋，協作緊密的人彼此並不相鄰，任何一條邊都橫穿半個畫布。就算 GPU 能畫
   10 萬條邊，畫出來也是一團漿糊。Obsidian 圖的可讀性來自力導向佈局讓社群
   自然聚簇、絕大多數邊變成短邊 —— **這是視覺問題的根因，和幀率問題同等重要**。

3. **JSON + graphology 雙重中間表示。** 19.4MB JSON 的解析本身就是秒級主線程
   阻塞；graphology 給 13 萬條邊每條建一個屬性對象（駐留內存粗估 100MB+ 量級），
   而渲染路徑最終只需要 8MB 的 typed array。graphology 在渲染路徑上純屬過路稅
   ——`buildCosmosPayload` 又通過 `extremities()` + `getEdgeAttribute()` 逐條
   把它讀回數組。

4. **懸停觸發 O(E) 重建。** 每次 mouseover/mouseout 重算全部邊的顏色/寬度數組
   並整體重上傳。global 的 3,797 條邊無感，但一旦邊數放開到 10 萬級，懸停本身
   就會製造掉幀 —— 恰好發生在用戶最敏感的交互瞬間。GC 壓力同源。

5. **次要問題**（順手記錄）：
   - `buildCosmosPayload` 依賴 `personNameMode`，切換簡繁會整體重建幾何數據，
     標籤映射和幾何應拆開。
   - `Math.min(...xs)` 對 21K 元素展開，節點量再漲會爆調用棧；邊界應在服務端算好。
   - 節點 JSON（3.88MB）逐行帶 `infobox` 提取的三種名字，可下發一次、與幾何分離。

### 1.4 對照：Obsidian Graph View 憑什麼流暢

- WebGL（Pixi.js）buffer 渲染，節點/邊全量駐留 GPU；
- 力導向佈局（Barnes-Hut 近似）讓圖有社群結構，邊短而局部；
- 縮放 LOD 靠 **alpha 淡出** 而非增刪幾何 —— 不重建 buffer；
- 懸停高亮 = 鄰接表查一跳鄰居 + 全局調暗，GPU 側改透明度；
- 標籤過縮放閾值才淡入，且只畫視口內的。

值得指出：Obsidian 在 2 萬節點以上同樣會明顯降幀（它的力導向在 CPU 跑）。
而 Cosmos.gl 是 GPU 力導向 + GPU 渲染 —— **當前選型的天花板本來就高於
Obsidian，問題全在我們的喂數據管線**。

---

## 2. 同類項目調研（2026-07-06）

對 GitHub 上有代表性的大規模「星雲圖」項目做了橫向閱讀，結論按對本項目的
影響力排序：

### 2.1 調研摘要

| 項目 | 規模 | 佈局 | 傳輸格式 | 渲染 | 對本項目的啟示 |
|---|---|---|---|---|---|
| [anvaka/pm（Software Galaxies）](https://github.com/anvaka/pm) | 最大 110 萬節點 60fps | **離線**（ngraph.offline.layout；>20 萬節點用 C++ 的 ngraph.native） | `positions.bin` + `links.bin` 二進制 + `labels.json`（ngraph.tobinary） | WebGL（ngraph.pixel/VivaGraph） | 與本方案 Phase 2/3 完全同構，是十年驗證過的成熟路線；直接借它的文件切分約定 |
| [anvaka/map-of-github](https://github.com/anvaka/map-of-github) | 69 萬倉庫 | **Leiden 聚類 → 兩級分層力導向**（簇內一次、簇間一次） | GeoJSON → tippecanoe 矢量瓦片 | MapLibre（地圖引擎） | 兩級分層佈局是治「冪律圖力導向縮成毛球」的成熟解法，直接併入 Phase 3；地圖瓦片路線本身不適合本項目（見 2.2） |
| [cosmos.gl v3](https://github.com/cosmograph-org/cosmos/releases)（現用 2.6.4） | 數十萬點邊實時模擬 | GPU | typed array | regl → **luma.gl / WebGL2** | v3 新增 `highlightedPointIndices` / `highlightedLinkIndices` / `getConnectedLinkIndices` / `getConnectedPointIndices`、模擬與渲染分離、GPU 過渡動畫、空間哈希碰撞檢測 —— **懸停高亮不用自己造了**，升級即得 |
| [platers/MAL-Map](https://github.com/platers/MAL-Map) | MAL/AniList 動畫關係圖 | 離線 D3-Force（Node 後端，迭代式簇分裂）+ CDlib 模塊度聚類 | 靜態 JSON/TXT | PIXI.js | 動漫領域直接先例：同樣走「離線聚類 + 離線力導向 + 靜態數據」路線，佐證方向；其漸進分裂佈局是 Phase 3 的備選算法 |
| [nomic-ai/deepscatter](https://github.com/nomic-ai/deepscatter) | 十億級點 | 外部預計算 | **四叉樹瓦片化 Apache Arrow**，按縮放漸進加載 | regl | 點的瓦片化已是解決了的問題，但**它根本不畫邊** —— 印證「邊的瓦片化」才是全量圖（Phase 5）的真正難點 |
| [ericdrowell/ElGrapho](https://github.com/ericdrowell/ElGrapho) | 百萬級 | Hairball 等線性時間佈局 | typed array | WebGL | 佐證「百萬邊在瀏覽器可行」；其線性佈局質量不如力導向，不採納 |

### 2.2 三條驗證了的結論

1. **「離線佈局 + 二進制傳輸 + GPU 渲染」是所有成功大圖項目的公共骨架。**
   anvaka 系、MAL-Map、deepscatter 無一例外把佈局挪出瀏覽器、把 JSON 換成
   二進制。本方案 Phase 2/3 不是新發明，是行業標準做法，可放心投入。
2. **冪律圖直接跑單級力導向必縮成毛球，成熟解法是「聚類 → 簇間佈局 → 簇內
   佈局」兩級分層。** map-of-github 在 69 萬節點上驗證過；MAL-Map 用迭代簇
   分裂達到同樣效果。原方案 Phase 3 的單級 FR/DrL 風險（§5）由此有了確定
   解法，升級為分層佈局。
3. **「圖當地圖渲染」（MapLibre + 矢量瓦片）不適合本項目主視圖。**
   它免費換來 LOD/標籤/剔除/CDN 緩存，但邊在地圖引擎裡是二等公民 ——
   map-of-github 全局視圖基本不畫邊。本產品**邊就是產品**（協作關係），
   放棄該路線作為主渲染器；其瓦片思想僅保留給 Phase 5 預案。

---

## 3. 技術路線比較

| 路線 | 內容 | 判斷 |
|---|---|---|
| A. 保留 Cosmos.gl 並升級 v3，重構管線 | 二進制傳輸 + 離線分層佈局 + 零分配 LOD + 內置 GPU 高亮 | **推薦**。改動集中在數據通路；調研確認此骨架是行業標準（§2.2） |
| B. 開啟 Cosmos GPU 實時模擬 | v3 `start()/pause()` 以預計算座標為初始值 | 作為 A 的可選增強（開場沉降動畫）；v3 模擬/渲染分離後實現成本比 v2 低 |
| C. 更換渲染器 | Sigma.js（已棄）、deck.gl、自研 Pixi（Obsidian/MAL-Map 路線）、WebGPU 庫 | 不推薦。cosmos v3 遷到 luma.gl/WebGL2 後現代性不輸任何備選；自研 Pixi 要數月才追平 |
| D. 圖當地圖（MapLibre + 矢量瓦片） | map-of-github 路線 | 主視圖不採納（邊是二等公民，§2.2）；瓦片思想留給 Phase 5 |
| E. 服務端視口切邊（edge tiles） | 按視口/縮放級從 DuckDB 動態取邊 | 僅當要上屏 2,600 萬條完整圖時才需要；518K 可視層整包下發足夠 |

結論：**A 為主幹，B 作可選開關，D/E 留作全量圖預案，C 排除。**

---

## 4. 推薦架構（方案 A）詳細設計

### 4.1 目標數據流

```
DuckDB（離線分層力導向座標 + Leiden 社群 + 按強度排序的邊）
  → FastAPI 二進制端點（positions/links/meta 三段式，snapshot 級 immutable 緩存）
  → 前端 DataView 零解析切片 → typed arrays
  → Cosmos.gl v3（一次上傳；LOD = subarray 前綴切片；高亮 = 內置 highlighted API）
```

graphology 徹底退出渲染路徑（NodePanel 的鄰居查詢改用 CSR 鄰接表或走 API）。

### 4.2 Phase 1 — 升級 cosmos.gl v3 + 渲染管線止血（前端，2–3 天）

不改協議、不改數據庫，先消滅 O(E) 重建：

1. **升級 `@cosmos.gl/graph` 2.6.4 → 3.x。** v3 遷至 luma.gl（WebGL2）、
   GPU 位置/顏色/尺寸過渡、空間哈希碰撞。注意破壞性變更：選中/高亮從命令式
   （`selectPointByIndex`）改為配置式（`highlightedPointIndices` 等），
   且「點置灰不再自動置灰關聯邊」—— 現有 `pointGreyoutOpacity` 邏輯需對照
   遷移指南重寫。
2. **懸停高亮改用 v3 內置 API，不再重建 buffer：**
   懸停節點 → `getConnectedLinkIndices` / `getConnectedPointIndices` 取一跳
   鄰域 → 設 `highlightedPointIndices` + `highlightedLinkIndices`，其餘自動
   調暗，全程 GPU 側。複雜度 O(deg)，原 `applyHoverEdgeFocus` 的 O(E)
   重建整段刪除。
3. **邊按強度降序駐留**（API 已經 `ORDER BY shared_works_count DESC`）。
   為每個 LOD 檔位預計算前綴長度，縮放時
   `cosmos.setLinks(links.subarray(0, n * 2))` —— 零拷貝視圖，無 filter、
   無分配。`linkColors` / `linkWidths` 全量算一次，同樣前綴切。
4. **loader 直出 typed array**，跳過 graphology；標籤映射與幾何拆開，
   簡繁切換只換 `Map<string,string>`。
5. **放開邊預算試水**：global 的 `min_shared` 下調（12 → 2~3，約 3,800 →
   數萬條邊），LOD 從「硬閾值」改為「按當前縮放給邊數預算，取強度前 N」。
   此階段即可驗證 v3 在本項目數據上的真實吞吐上限。

### 4.3 Phase 2 — 二進制傳輸（後端協議，約 1 週）

借用 anvaka `ngraph.tobinary` 的三件套約定（十年驗證過的格式思路），
按本項目需求裁剪為單請求分段 buffer：

新端點 `GET /api/graph/buffers`（單一全量圖，不再分檔，見 §4.5），
單個 ArrayBuffer：

```
[header: magic + version + nodeCount + edgeCount + 各段偏移]
[positions  : Float32Array  nodeCount×2]   ← 服務端已歸一化到 Cosmos 空間
[sizes      : Float32Array  nodeCount]
[colors     : Uint8Array    nodeCount×4]   ← 顏色邏輯移到服務端/構建期
[community  : Uint16Array   nodeCount]     ← Leiden 社群 id（Phase 3 產出）
[edgePairs  : Uint32Array   edgeCount×2]   ← 節點索引（非字符串 ID）
[edgeWeights: Float32Array  edgeCount]     ← collaboration_score
[edgeShared : Uint16Array   edgeCount]     ← shared_works_count（LOD 用）
```

- 節點的名字/度數等**元數據走另一個 JSON 端點**（對應 anvaka 的
  `labels.json`），與幾何解耦；懸停標籤只需 id→name 映射。
- 518K 邊全量：pairs 4.1MB + weights 2MB + shared 1MB + 節點段 ~0.5MB ≈
  **7.6MB 裸 / 約 3MB gzip**，對比現在 l0 一層就 19.4MB JSON；解析成本歸零
  （`new Float32Array(buf, offset, len)`）。
- 以 snapshot id 做 `ETag` + `Cache-Control: immutable`，二訪零流量。
- 實現上用 DuckDB 直接吐列（`fetchnumpy()` → `.tobytes()`）拼段即可；
  Apache Arrow IPC 是備選（deepscatter 用它做瓦片證明了可行性），
  首版建議裸 buffer + version 字節，夠用且無依賴。

### 4.4 Phase 3 — 離線分層力導向佈局（視覺根治，約 1 週）

把 `deterministic_spiral_v1` 換成**構建期分層佈局**（map-of-github 配方，
治毛球的成熟解法）：

1. **先聚類再佈局，兩級進行：**
   1. Leiden 社群檢測（python-igraph 原生支持），填上 `graph_nodes.community_id`
      （schema 裡這個佔位列至今是 NULL）；
   2. **簇間佈局**：把每個社群縮成超節點（簇間邊權 = 跨簇協作分之和），
      對這張百級節點的小圖跑力導向，得到各簇質心；
   3. **簇內佈局**：每個社群內部單獨跑帶邊權的 FR / FA2（幾百到幾千節點，
      秒級），平移縮放到簇質心周圍的預算半徑內。
2. 寫回 `graph_nodes.x/y`，`layout_method` 版本化（如 `hier_leiden_fr_v1`）。
   工具鏈與現有 Python 管線同棧（igraph + leidenalg），21K 節點分鐘級。
   備選：MAL-Map 的迭代簇分裂 D3-Force、或 >20 萬節點時換 ngraph.native。
3. 前端按 `community` 段做低飽和度色相偏移 —— 即 Obsidian 的 group 著色。
4. 佈局聚簇後，絕大多數強邊變成簇內短邊，現有
   `linkVisibilityDistanceRange`（按屏幕長度淡出長邊）才真正開始起作用，
   10 萬級邊的畫面從「漿糊」變成「星雲」。

### 4.5 視圖整合 — global/l0/l1 三檔併為單一星雲

三檔圖層是舊管線「一次喂不動 518K 邊」的防禦性切片（global 砍邊、l0 砍
節點、l1 折中），Phase 1–3 落地後瓶頸消失，**合併為一張全量圖**：

- 一次下發 21K 節點 + 518K 邊（≈3MB gzip），縮放 LOD 前綴切片連續過渡，
  對齊 Obsidian「永遠只有一張圖」的形態；
- 三檔語義降級為**客戶端過濾器**（數據已全量在本地，過濾零成本）：
  最小度數滑桿（v3 greyout，替代 l0「核心」）、邊強度預算滑桿
  （LOD 前綴長度手動檔，替代 l1「細節」），對應 Obsidian 的過濾面板；
- 刪除面：後端 `LEVELS` 配置與 `/api/graph/{level}/nodes|edges` 三檔六查詢
  → 單一 buffers 端點；前端 `loadLevel` 三份緩存、`GraphLevelToggle`、
  `?level=` 路由、`minSharedForZoom` 分檔、`buildEdgeArrays` 的 level
  三元分支全部移除（delete, don't deprecate）；
- **person 個人星系與 Constellation 尋路視圖保留** —— 它們是產品功能差異
  （自我中心網絡 / 路徑查找），不是性能切片。

此項應與 Phase 2 一同交付（協議定型時直接不做分檔）。

### 4.6 Phase 4 — 標籤與交互打磨（2–3 天）

- **縮放閾值標籤**：現在 global 層完全沒有常駐標籤。用**單個 canvas 疊加層**
  （不是 DOM 節點——21K 個 div 不可行）：僅交互期間 rAF 節流，用 positions
  數組 + 當前變換做視口剔除，畫視口內度數 top-K 的名字，隨縮放級調整 K 與
  字號透明度。簇級標籤（社群名，如「吉卜力系」「京都動畫系」）可借
  map-of-github 思路後續人工/半自動命名。
- 點擊節點：`getConnectedPointIndices` 一跳高亮 + 其餘調暗（與懸停同機制），
  對齊 Obsidian 的焦點體驗。
- 可選：v3 `start()` 實時模擬開關（方案 B），以離線座標為初始位置，
  開場跑 2–3 秒沉降後 `pause()`，提供「活的星雲」質感。

### 4.7 Phase 5（預案，不排期）— 完整 2,600 萬邊圖

26M 邊無法也不應下發瀏覽器。調研結論：點的瓦片化是已解問題
（deepscatter 四叉樹 Arrow 瓦片到十億級），**邊的瓦片化沒有現成輪子**，
需自研「按強度分位數 × 空間格網」的邊瓦片。若未來產品確有此需求：

- 構建期按強度分位數預生成多級邊 LOD 表（L0 全局骨幹 → Ln 局部細節）；
- 視口驅動取邊：按節點座標空間過濾（DuckDB 對 x/y 建 min-max 索引即可），
  進入某簇時增量拉當地邊；
- 維持現有產品哲學：**默認圖保持稀疏可讀，完整證據永遠可查** ——
  518K 可視層作為上屏上限是合理的產品決策，不是技術妥協。

---

## 5. 驗收指標

| 指標 | 現狀 | 目標 |
|---|---|---|
| global 常駐可見邊 | 144–3,797 條 | ≥ 50K 條（強度前綴），縮放連續過渡 |
| 平移/縮放幀率（核顯） | 未測（邊少時流暢） | 60fps，主線程無 >16ms 任務 |
| 懸停高亮成本 | O(E) 重建 + 全量重上傳 | O(deg)（v3 內置 API），<1ms 腳本時間 |
| 圖層數據 | 三檔切片，l0/l1 邊各 19.4 / 17.7 MB JSON | 單一全量圖，518K 邊 ≤ 3MB gzip 二進制 |
| 圖層 UI | global/l0/l1 手動切換 | 無檔位；連續縮放 + 度數/邊強度過濾器 |
| 冷加載可交互 | ~0.8–2.0s | ≤ 1.5s（含全量邊） |
| 視覺聚簇 | 無（螺旋） | Leiden 分層佈局 + 社群著色 |

測量沿用 `runtimeMetrics`（`cosmos-ready` 已有），Phase 1 起補充：
交互期 fps 採樣、hover 的 `performance.mark`、Chrome tracing 抽查長任務。
每個 Phase 完成後在 `reports/graph-performance.md` 追加一節對照數據。

## 6. 風險與注意事項

- **cosmos.gl v3 遷移面**：選中/高亮 API 全部換掉（命令式→配置式）、
  regl→luma.gl 可能帶來配置項增刪，`CosmosGalaxyView` 的事件與聚焦邏輯
  需整體過一遍遷移指南；Phase 1 首日先做 spike 驗證 `setLinks` 接受
  subarray 視圖 + v3 高亮 API 行為。若 subarray 被內部持有引用，退化為
  每個 LOD 檔位預切一份（518K 邊也只是幾份 4MB）。
- **分層佈局的簇間邊觀感**：兩級佈局會把跨簇長邊拉得更顯眼（這是特性也是
  噪音），需靠 `linkVisibilityDistanceRange` + 強度 alpha 調參；用宮崎駿/
  京都動畫等已知社群人工抽查簇的語義正確性。
- **`min_shared` 放開後的視覺密度**：邊數預算制（按縮放給 N）必須與
  Phase 3 佈局配合調參；Phase 1 先放到數萬條驗證幀率即可，不追求好看。
- **緩存失效**：二進制端點必須綁定 snapshot id，換 Archive 快照後
  ETag 自動失效，避免舊座標配新元數據。
- Phase 之間彼此獨立可交付：1 先行止血，2/3 可並行，4 收尾。
  全程不動 person 視圖（僅 94 節點，無性能問題）與 Constellation 視圖。

## 附：調研來源

- https://github.com/anvaka/pm （Software Galaxies：離線佈局 + 二進制三件套）
- https://github.com/anvaka/map-of-github （Leiden + 兩級分層佈局 + 矢量瓦片）
- https://github.com/cosmograph-org/cosmos （v3 releases：luma.gl、highlighted API、模擬/渲染分離）
- https://github.com/platers/MAL-Map （動漫領域先例：離線聚類 + 離線力導向 + PIXI）
- https://github.com/nomic-ai/deepscatter （四叉樹 Arrow 瓦片，十億級點、無邊）
- https://github.com/ericdrowell/ElGrapho （百萬級 WebGL 圖，線性佈局）
