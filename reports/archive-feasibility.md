# Bangumi Archive Feasibility Analysis

## Snapshot

Source:

- `bangumi/Archive`, cloned locally at `data/raw/bangumi-archive`
- Latest release URL from `aux/latest.json`
- Snapshot zip: `data/raw/dump-2026-05-19.210434Z.zip`
- Created at: `2026-05-19T21:04:35Z`
- Zip size: `404,069,971` bytes
- Verified SHA-256: `051a6b7a4cbf1208ca74194135a2ed2feb5eca702bc87a12192c0cc99e233198`

The zip expands to about `1.69GB` of JSON Lines data.

## Archive Structure

The release zip contains:

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

Important correction: `subject-persons.jsonlines` stores `position` as a numeric constant, not a raw text label.

Example:

```json
{"person_id":45228,"subject_id":1,"position":2004,"appear_eps":""}
```

The position mapping lives in `bangumi/common`:

```text
data/raw/bangumi-common/subject_staffs.yml
```

For anime subjects, staff position ids include:

- `2`: 导演
- `4`: 分镜
- `5`: 演出
- `10`: 系列构成
- `14`: 总作画监督
- `20`: 原画
- `21`: 第二原画
- `44`: 音响监督
- `54`: 制片人
- `87`: 动画制片人

## Base Counts

From the 2026-05-19 snapshot:

| Metric | Count |
| --- | ---: |
| Total subjects | 637,505 |
| Anime subjects, `subject.type = 2` | 29,742 |
| Total persons | 93,579 |
| Real individual persons, `person.type = 1` | 83,565 |
| Total subject-person rows | 1,987,926 |
| Anime credits involving real individual people | 859,791 |
| Real people with anime credits | 42,317 |
| Anime subjects with real person credits | 19,617 |

Subject counts by type:

| Type | Count |
| ---: | ---: |
| 1 | 397,723 |
| 2 | 29,742 |
| 3 | 97,656 |
| 4 | 87,036 |
| 6 | 25,348 |

Person counts by type:

| Type | Count |
| ---: | ---: |
| 0 | 1 |
| 1 | 83,565 |
| 2 | 7,788 |
| 3 | 2,225 |

## Top Anime Staff Positions

Top position ids among anime credits involving real individual people:

| Count | Position |
| ---: | --- |
| 225,236 | `20` 原画 |
| 85,918 | `15` 作画监督 |
| 49,433 | `21` 第二原画 |
| 46,712 | `4` 分镜 |
| 46,249 | `5` 演出 |
| 27,223 | `51` 补间动画 |
| 25,300 | `3` 脚本 |
| 18,704 | `54` 制片人 |
| 16,380 | `2` 导演 |
| 14,637 | `35` 企画 |
| 13,840 | `8` 人物设定 |
| 12,755 | `42` 製作 |
| 11,081 | `6` 音乐 |
| 10,861 | `14` 总作画监督 |
| 9,870 | `1` 原作 |
| 9,847 | `11` 美术监督 |
| 9,368 | `28` 剪辑 |
| 9,313 | `33` 主题歌演出 |
| 8,785 | `25` 背景美术 |
| 8,577 | `17` 摄影监督 |
| 8,469 | `44` 音响监督 |
| 8,101 | `82` 摄影 |
| 7,987 | `56` 制作进行 |
| 7,637 | `13` 色彩设计 |
| 7,158 | `90` 作画监督助理 |

## Initial Role Mapping Counts

Using the MVP Tier A/B/C mapping:

| Normalized Role | Count |
| --- | ---: |
| key_animation | 225,236 |
| animation_director | 85,918 |
| second_key_animation | 49,433 |
| storyboard | 46,712 |
| episode_director | 46,249 |
| script | 25,300 |
| producer | 18,704 |
| director | 18,218 |
| character_design | 13,840 |
| music | 11,081 |
| chief_animation_director | 10,861 |
| art_director | 9,847 |
| photography_director | 8,577 |
| sound_director | 8,469 |
| production_assistant | 7,987 |
| series_composition | 6,164 |
| animation_producer | 4,477 |
| assistant_director | 1,853 |
| setting_production | 1,499 |

Unmapped or intentionally excluded credits in this first mapping: `259,366`.

That is acceptable for MVP because the first visible graph is not meant to include every possible role. The formal audit should still report the unmapped distribution so role tiers can be refined.

## Candidate Graph Scale

The following rough pass deduplicated each subject-person to a max role weight per layer before pair projection.

### Tier A Only

| Metric | Count |
| --- | ---: |
| Subjects | 16,939 |
| Persons | 11,981 |
| Estimated pair contributions | 270,351 |
| Unique edges | 190,645 |
| Nodes with edges | 11,571 |
| Edges with `sharedWorksCount >= 2` | 41,699 |
| Median degree | 16 |
| P95 degree | 118 |
| Max degree | 1,168 |
| Top 5 strongest neighbors per node | 43,475 edges |
| Top 10 strongest neighbors per node | 72,688 edges |
| Top 20 strongest neighbors per node | 110,024 edges |

Largest Tier A subject by mapped staff count:

- `116370` 日本アニメ（ーター）見本市 / 日本动画（人）博览会, 52 people

### Tier A + Tier B

| Metric | Count |
| --- | ---: |
| Subjects | 17,752 |
| Persons | 22,745 |
| Estimated pair contributions | 4,621,212 |
| Unique edges | 3,215,208 |
| Nodes with edges | 22,489 |
| Edges with `sharedWorksCount >= 2` | 744,605 |
| Median degree | 114 |
| P95 degree | 1,141 |
| Max degree | 7,610 |
| Top 5 strongest neighbors per node | 100,290 edges |
| Top 10 strongest neighbors per node | 189,887 edges |
| Top 20 strongest neighbors per node | 350,298 edges |

Largest Tier A+B subject by mapped staff count:

- `899` 名探偵コナン / 名侦探柯南, 281 people

### Tier A + Tier B + Tier C

| Metric | Count |
| --- | ---: |
| Subjects | 17,912 |
| Persons | 30,068 |
| Estimated pair contributions | 24,474,952 |
| Max people on one subject | 578 |

Full unique edge aggregation was intentionally skipped for this rough pass because the estimated pair contribution count exceeded the temporary safety limit of `8,000,000`.

Largest Tier A+B+C subject by mapped staff count:

- `400602` 葬送のフリーレン / 葬送的芙莉莲, 578 people

## Feasibility Conclusion

The product is feasible, but only with the two-layer design.

Recommended MVP data path:

1. Import full evidence into DuckDB.
2. Use `subject_staffs.yml` to map numeric staff positions.
3. Preserve all anime-person-position evidence.
4. Generate the default graph from Tier A first.
5. Consider Tier A+B for local expansion or a later denser graph, not as the first global backbone.
6. Keep Tier C out of the default global graph and use it for evidence lookup only.

Recommended first visible graph setting:

```text
Role layer: Tier A
Initial pruning: sharedWorksCount >= 2 OR top 10 strongest neighbors per node
Expected visible range: roughly 11.5k nodes and 70k-110k edges before further score threshold tuning
```

Why not Tier A+B as the first default graph:

- It creates 3.2M unique candidate edges.
- Even top 10 keeps about 190k edges.
- Degree distribution is much more extreme, with max degree over 7,600.
- It may be useful after zooming or community selection, but is too dense as a first global view.

Why not Tier A+B+C:

- The pair contribution estimate is already about 24.5M for the limited C roles.
- Key animation alone contributes 225k credits.
- It should remain in the evidence layer and two-person comparison query path.

## Required Spec Changes

The original audit plan assumed raw staff positions might be text. That is wrong for the current Archive dump.

The formal audit implementation must:

- Detect or download the release zip pointed to by `aux/latest.json`.
- Read JSON Lines from inside the zip.
- Clone or accept a path to `bangumi/common`.
- Load `subject_staffs.yml`.
- Store both `position_id` and mapped labels.
- Normalize from position id to role tier.
- Avoid materializing A+B+C all-pair tables unless explicit limits allow it.

## Local Environment Notes

`jq` is available.

The current Python environment does not have `duckdb` or `polars` installed yet:

```text
ModuleNotFoundError: No module named 'duckdb'
```

So the implementation phase should add a project dependency setup, likely via `pyproject.toml`, before building the formal pipeline.

