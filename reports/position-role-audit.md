# Bangumi Anime Position Tier Audit

只审核 `subject.type = 2` 动画相关职位。所有 anime staff position 现在都有 Staff Galaxy tier；声优/配音来自 `person-characters`，单独作为 CAST 层。

## Tier Summary

| Tier | Staff Position Types | Anime Credits | Meaning |
| --- | ---: | ---: | --- |
| A | 21 | 127,892 | 默认全局骨架候选：核心主创、原作/原案、企画、核心制片 |
| B | 42 | 278,615 | 局部扩展和详情重点：部门负责人、核心单项创作、重要制片/监督类 |
| C | 80 | 399,222 | 普通详情：具体执行岗位、设计/声音/影像/歌曲等参与证据 |
| D | 26 | 54,062 | 加载更多：协力、助理、长尾、高噪声或委员会/实体型关系 |

## CAST Layer

| Layer | Rows | People | Anime Subjects | Meaning |
| --- | ---: | ---: | ---: | --- |
| CAST / `voice_cast` | 152,390 | 9,557 | 10,086 | 声优/配音，独立于 STAFF tier，用于人物详情和双人完整关系 |

## Unknown Cross-Type Positions Attached To Anime Subjects

这些不是 anime staff 常量，但出现在动画条目的 `subject-persons` 中，已保留为 Tier D。

| Position ID | Normalized Role | Anime Credits |
| ---: | --- | ---: |
| 4003 | `unknown_position_4003` | 8 |
| 4002 | `unknown_position_4002` | 6 |
| 4004 | `unknown_position_4004` | 2 |
| 1028 | `unknown_position_1028` | 1 |
| 1015 | `unknown_position_1015` | 1 |
| 4014 | `unknown_position_4014` | 1 |

## Current Anime Staff Tier Mapping

| Tier | Position ID | CN | EN | Normalized Role | Weight | Anime Credits |
| --- | ---: | --- | --- | --- | ---: | ---: |
| A | 1 | 原作 | Original Creator/Original Work | `original_creator` | 9 | 9,870 |
| A | 2 | 导演 | Director/Direction | `director` | 10 | 16,380 |
| A | 6 | 音乐 | Music | `music` | 5 | 11,081 |
| A | 7 | 人物原案 | Original Character Design | `original_character_design` | 6 | 3,555 |
| A | 8 | 人物设定 | Character Design | `character_design` | 7 | 13,840 |
| A | 10 | 系列构成 | Series Composition | `series_composition` | 8 | 6,164 |
| A | 14 | 总作画监督 | Chief Animation Director | `chief_animation_director` | 7 | 10,861 |
| A | 29 | 原案 | Original Plan | `original_plan` | 6 | 1,206 |
| A | 35 | 企画 | Planning | `planning` | 6 | 14,637 |
| A | 36 | 企划制作人 | Planning Producer | `planning_producer` | 6 | 348 |
| A | 41 | 系列监督 | Series Production Director | `series_production_director` | 8 | 465 |
| A | 49 | 联合导演 | Co-Director | `co_director` | 8 | 894 |
| A | 52 | 执行制片人 | Executive Producer | `executive_producer` | 6 | 4,699 |
| A | 54 | 制片人 | Producer | `producer` | 6 | 18,704 |
| A | 58 | 总制片人 | Chief Producer | `chief_producer` | 6 | 3,130 |
| A | 72 | 副导演 | Assistant Director | `assistant_director` | 8 | 1,853 |
| A | 74 | 总导演 | Chief Director | `chief_director` | 10 | 1,838 |
| A | 80 | 监制 | Supervising Producer | `supervising_producer` | 6 | 3,386 |
| A | 87 | 动画制片人 | Animation Producer | `animation_producer` | 8 | 4,477 |
| A | 121 | 创意制片人 | Creative Producer | `creative_producer` | 6 | 36 |
| A | 123 | 制作统括 | Chief Production Supervisor | `chief_production_supervisor` | 5 | 468 |
| B | 3 | 脚本 | Script/Screenplay | `script` | 4 | 25,300 |
| B | 4 | 分镜 | Storyboard | `storyboard` | 4 | 46,712 |
| B | 5 | 演出 | Episode Direction | `episode_director` | 4 | 46,249 |
| B | 11 | 美术监督 | Art Direction | `art_director` | 3 | 9,847 |
| B | 13 | 色彩设计 | Color Design | `color_design` | 3 | 7,637 |
| B | 15 | 作画监督 | Animation Direction | `animation_director` | 3 | 85,918 |
| B | 17 | 摄影监督 | Director of Photography | `photography_director` | 3 | 8,577 |
| B | 18 | 监修 | Supervision/Supervisor | `supervisor` | 4 | 1,586 |
| B | 28 | 剪辑 | Editing | `editing` | 3 | 9,368 |
| B | 44 | 音响监督 | Sound Director | `sound_director` | 3 | 8,469 |
| B | 48 | 配音监督 | ADR Director | `adr_director` | 3 | 1,381 |
| B | 53 | 助理制片人 | Assistant Producer | `assistant_producer` | 3 | 1,464 |
| B | 59 | 联合制片人 | Co-Producer | `co_producer` | 3 | 332 |
| B | 69 | CG 导演 | CG Director | `cg_director` | 3 | 1,785 |
| B | 70 | 机械作画监督 | Mechanical Animation Direction | `mechanical_animation_director` | 3 | 1,063 |
| B | 71 | 美术设计 | Art Design | `art_design` | 3 | 5,573 |
| B | 73 | OP・ED 分镜 | OP ED | `op_ed_storyboard` | 3 | 5,959 |
| B | 77 | 动作作画监督 | Action Animation Direction | `action_animation_director` | 3 | 764 |
| B | 85 | 音乐制作人 | Music Producer | `music_producer` | 3 | 2,066 |
| B | 86 | 3DCG 导演 | 3DCG Director | `3dcg_director` | 3 | 710 |
| B | 88 | 特效作画监督 | Special Effects Animation Direction | `special_effects_animation_director` | 3 | 415 |
| B | 89 | 主演出 | Chief Episode Direction | `chief_episode_direction` | 3 | 218 |
| B | 92 | 主动画师 | Main Animator | `main_animator` | 3 | 1,175 |
| B | 101 | 技术导演 | Technical Director | `technical_director` | 3 | 78 |
| B | 102 | 特技导演 |  | `tokusatsu_director` | 3 | 20 |
| B | 106 | 副人物设定 | Sub-Character Design | `sub_character_design` | 3 | 1,520 |
| B | 116 | 音乐监督 | Music Director | `music_director` | 3 | 678 |
| B | 122 | 副制片人 | Associate Producer | `associate_producer` | 3 | 718 |
| B | 124 | 现场制片人 | Line Producer | `line_producer` | 3 | 110 |
| B | 128 | OP・ED 演出 | OP・ED Direction | `op_ed_direction` | 3 | 1,870 |
| B | 133 | 视觉导演 | Visual Director | `visual_director` | 3 | 51 |
| B | 134 | 创意总监 | Creative Supervisor/Director | `creative_supervisor_director` | 3 | 45 |
| B | 137 | 动作导演 |  | `action_director` | 3 | 104 |
| B | 140 | 角色作画监督 | Character Animation Director | `character_animation_director` | 3 | 95 |
| B | 141 | 作画监修 | Animation Supervisor | `animation_supervisor` | 3 | 79 |
| B | 150 | 副系列构成 | Associate Series Composition | `associate_series_composition` | 3 | 10 |
| B | 158 | CG 制作人 | CG Producer | `cg_producer` | 3 | 109 |
| B | 159 | 宣传制片人 | Publicity Producer | `publicity_producer` | 3 | 88 |
| B | 160 | 美术制作人 | Art Producer | `art_producer` | 3 | 4 |
| B | 161 | 音响制作人 | Sound Producer | `sound_producer` | 3 | 39 |
| B | 164 | 美术监督助理 | Assistant Art Director | `assistant_art_director` | 3 | 170 |
| B | 166 | 摄影监督助理 | Assistant Director of Photography | `assistant_photography_director` | 3 | 259 |
| C | 9 | 构图 | Layout | `layout` | 1 | 2,126 |
| C | 16 | 机械设定 | Mechanical Design | `mechanical_design` | 1 | 2,851 |
| C | 19 | 道具设计 | Prop Design | `prop_design` | 1 | 4,087 |
| C | 20 | 原画 | Key Animation | `key_animation` | 1 | 225,236 |
| C | 21 | 第二原画 | 2nd Key Animation | `second_key_animation` | 1 | 49,433 |
| C | 22 | 动画检查 | Animation Check | `animation_check` | 1 | 6,825 |
| C | 25 | 背景美术 | Background Art | `background_art` | 1 | 8,785 |
| C | 26 | 色彩指定 | Color Setting | `color_setting` | 1 | 5,491 |
| C | 30 | 主题歌编曲 | Theme Song Arrangement | `theme_song_arrangement` | 1 | 5,028 |
| C | 31 | 主题歌作曲 | Theme Song Composition | `theme_song_composition` | 1 | 5,708 |
| C | 32 | 主题歌作词 | Theme Song Lyrics | `theme_song_lyrics` | 1 | 5,503 |
| C | 33 | 主题歌演出 | Theme Song Performance | `theme_song_performance` | 1 | 9,313 |
| C | 34 | 插入歌演出 | Inserted Song Performance | `inserted_song_performance` | 1 | 1,920 |
| C | 37 | 制作管理 | Production Manager | `production_manager` | 1 | 3,294 |
| C | 39 | 录音 | Recording | `recording` | 1 | 2,816 |
| C | 43 | 设定 | Setting | `setting` | 1 | 3,385 |
| C | 45 | 音响 | Sound | `sound` | 1 | 1,882 |
| C | 46 | 音效 | Sound Effects | `sound_effects` | 1 | 5,824 |
| C | 47 | 特效 | Special Effects | `special_effects` | 1 | 3,559 |
| C | 50 | 背景设定 | Setting | `background_setting` | 1 | 306 |
| C | 56 | 制作进行 | Assistant Production Manager | `production_assistant` | 1 | 7,987 |
| C | 57 | 演员监督 | Casting Director | `casting_director` | 1 | 57 |
| C | 65 | 音乐制作 | Music Work | `music_work` | 1 | 1,292 |
| C | 67 | 动画制作 | Animation Work | `animation_work` | 1 | 2,062 |
| C | 75 | 3DCG | 3DCG | `3dcg` | 1 | 1,982 |
| C | 82 | 摄影 | Photography | `photography` | 1 | 8,101 |
| C | 84 | 设定制作 | Design Manager | `setting_production` | 1 | 1,499 |
| C | 90 | 作画监督助理 | Assistant Animation Direction | `assistant_animation_director` | 1 | 7,158 |
| C | 91 | 演出助理 | Assistant Episode Direction | `assistant_episode_director` | 1 | 2,410 |
| C | 93 | 上色 |  | `finishing` | 1 | 2,997 |
| C | 94 | 上色检查 |  | `finishing_check` | 1 | 805 |
| C | 95 | 色彩检查 |  | `color_check` | 1 | 963 |
| C | 96 | 美术板 |  | `art_board` | 1 | 172 |
| C | 97 | 美术 |  | `art` | 1 | 503 |
| C | 98 | 印象板 |  | `image_board` | 1 | 102 |
| C | 99 | 2D 设计 | 2D WORKS | `2d_works` | 1 | 498 |
| C | 100 | 3D 设计 | 3D WORKS | `3d_works` | 1 | 20 |
| C | 103 | 色彩脚本 | Color Script | `color_script` | 1 | 58 |
| C | 104 | 分镜协力 |  | `storyboard_cooperation` | 1 | 187 |
| C | 107 | 客座人物设定 | Guest character design | `guest_character_design` | 1 | 148 |
| C | 108 | 构图监修 |  | `layout_supervision` | 1 | 101 |
| C | 109 | 构图作画监督 |  | `layout_animation_director` | 1 | 73 |
| C | 110 | 总作画监督助理 |  | `assistant_chief_animation_director` | 1 | 395 |
| C | 111 | 道具作画监督 |  | `prop_animation_director` | 1 | 61 |
| C | 112 | 概念设计 | Concept Design | `concept_design` | 1 | 133 |
| C | 113 | 服装设计 | Costume Design | `costume_design` | 1 | 301 |
| C | 114 | 标题设计 | Title Design | `title_design` | 1 | 43 |
| C | 115 | 设定协力 | Setting Cooperation | `setting_cooperation` | 1 | 288 |
| C | 117 | 选曲 | Music Selection | `music_selection` | 1 | 256 |
| C | 118 | 插入歌作词 | Inserted Song Lyrics | `inserted_song_lyrics` | 1 | 415 |
| C | 119 | 插入歌作曲 | Inserted Song Composition | `inserted_song_composition` | 1 | 460 |
| C | 120 | 插入歌编曲 | Inserted Song Arrangement | `inserted_song_arrangement` | 1 | 383 |
| C | 125 | 文艺制作 | Literary Producer | `literary_producer` | 1 | 145 |
| C | 129 | Bank 分镜演出 | Bank Storyboard Direction | `bank_storyboard_direction` | 1 | 66 |
| C | 130 | Live 分镜演出 | Live Storyboard Direction | `live_storyboard_direction` | 1 | 154 |
| C | 131 | 剧中剧分镜演出 | Meta-story Storyboard Direction | `meta_story_storyboard_direction` | 1 | 13 |
| C | 132 | 剧中剧人设 | Meta-story Character Design | `meta_story_character_design` | 1 | 17 |
| C | 135 | 特摄效果 | Tokusatsu Effects | `tokusatsu_effects` | 1 | 18 |
| C | 136 | 视觉效果 | Visual Effects | `visual_effects` | 1 | 164 |
| C | 138 | 转场绘 | Eyecatch Art | `eyecatch_art` | 1 | 105 |
| C | 139 | 插画 | Illustration | `illustration` | 1 | 1,773 |
| C | 142 | 机设原案 | Mechanical Design Concept | `mechanical_design_concept` | 1 | 17 |
| C | 143 | 概念艺术 | Concept Art | `concept_art` | 1 | 60 |
| C | 144 | 视觉概念 | Visual Concept | `visual_concept` | 1 | 23 |
| C | 145 | 画面设计 | Scene Design | `scene_design` | 1 | 25 |
| C | 146 | 怪物设计 | Monster Design | `monster_design` | 1 | 190 |
| C | 147 | 故事概念 | Story Concept | `story_concept` | 1 | 5 |
| C | 148 | 剧本协调 | Scenario Coordinator | `scenario_coordinator` | 1 | 1 |
| C | 149 | 脚本协力 | Script Cooperation | `script_cooperation` | 1 | 141 |
| C | 151 | 构成协力 | Series Composition Cooperation | `series_composition_cooperation` | 1 | 28 |
| C | 153 | 整音 | Sound Mixing | `sound_mixing` | 1 | 36 |
| C | 154 | 音响制作担当 | Sound Production Coordinator | `sound_production_coordinator` | 1 | 565 |
| C | 155 | 在线剪辑 | Online Editing | `online_editing` | 1 | 33 |
| C | 156 | 离线剪辑 | Offline Editing | `offline_editing` | 1 | 31 |
| C | 157 | 3D 动画师 | 3D Animator | `3d_animator` | 1 | 81 |
| C | 162 | CG 制作进行 | CG Production Coordinator | `cg_production_coordinator` | 1 | 37 |
| C | 163 | 美术制作进行 | Art Production Coordinator | `art_production_coordinator` | 1 | 11 |
| C | 165 | 色彩设计助理 | Assistant Color Designer | `assistant_color_designer` | 1 | 140 |
| C | 167 | 制作管理助理 | Assistant Production Desk | `assistant_production_desk` | 1 | 45 |
| C | 168 | 设定制作助理 | Assistant Design Manager | `assistant_design_manager` | 1 | 16 |
| D | 23 | 助理制片人 | Assistant Producer | `assistant_producer_legacy` | 0.25 | 686 |
| D | 24 | 制作助理 | Associate Producer | `associate_producer_assistant` | 0.25 | 124 |
| D | 27 | 数码绘图 | Digital Paint | `digital_paint` | 0.25 | 302 |
| D | 38 | 宣传 | Publicity | `publicity` | 0.25 | 1,195 |
| D | 40 | 录音助理 | Recording Assistant | `recording_assistant` | 0.25 | 795 |
| D | 42 | 製作 | Production | `anime_staff_42` | 0.25 | 12,755 |
| D | 51 | 补间动画 | In-Between Animation | `in_between_animation` | 0.25 | 27,223 |
| D | 55 | 音乐助理 | Music Assistant | `music_assistant` | 0.25 | 48 |
| D | 60 | 台词编辑 | Dialogue Editing | `dialogue_editing` | 0.25 | 1 |
| D | 61 | 后期制片协调 | Post-Production Assistant | `post_production_assistant` | 0.25 | 5 |
| D | 62 | 制作助理 | Production Assistant | `production_assistant_general` | 0.25 | 111 |
| D | 63 | 制作 | Production | `production` | 0.25 | 754 |
| D | 64 | 制作协调 | Production Coordination | `production_coordination` | 0.25 | 70 |
| D | 66 | 特别鸣谢 | Special Thanks | `special_thanks` | 0.25 | 1,569 |
| D | 76 | 制作协力 | Work Assistance | `work_assistance` | 0.25 | 3,430 |
| D | 81 | 协力 | Assistance | `assistance` | 0.25 | 3,287 |
| D | 83 | 制作进行协力 | Assistant Production Manager Assistance | `production_assistant_assistance` | 0.25 | 590 |
| D | 105 | 分镜抄写 |  | `storyboard_clean_up` | 0.25 | 28 |
| D | 127 | 企画协力 | Planning Cooperation | `planning_cooperation` | 0.25 | 834 |
| D | 152 | 录音工作室 | Recording Studio | `recording_studio` | 0.25 | 236 |

## All Anime Staff Positions From Bangumi Common

| Position ID | CN | EN | JP | Categories | Tier | Normalized Role | Anime Credits |
| ---: | --- | --- | --- | --- | --- | --- | ---: |
| 1 | 原作 | Original Creator/Original Work |  | 设定类 | A | `original_creator` | 9,870 |
| 2 | 导演 | Director/Direction | 監督 シリーズ監督 | 导演类 | A | `director` | 16,380 |
| 3 | 脚本 | Script/Screenplay | シナリオ | 分镜/脚本类 | B | `script` | 25,300 |
| 4 | 分镜 | Storyboard | コンテ  ストーリーボード  画コンテ  絵コンテ | 分镜/脚本类 | B | `storyboard` | 46,712 |
| 5 | 演出 | Episode Direction |  | 演出类 | B | `episode_director` | 46,249 |
| 6 | 音乐 | Music | 楽曲  音楽 | 声音类 | A | `music` | 11,081 |
| 7 | 人物原案 | Original Character Design | キャラ原案 | 设定类 | A | `original_character_design` | 3,555 |
| 8 | 人物设定 | Character Design | キャラ設定 | 设定类 | A | `character_design` | 13,840 |
| 9 | 构图 | Layout | レイアウト | 演出类 | C | `layout` | 2,126 |
| 10 | 系列构成 | Series Composition | シナリオディレクター  構成  シリーズ構成  脚本構成 | 分镜/脚本类 | A | `series_composition` | 6,164 |
| 11 | 美术监督 | Art Direction | 美術監督 アートディレクション 背景監督 | 美术类 / 导演类 | B | `art_director` | 9,847 |
| 13 | 色彩设计 | Color Design | 色彩設定 | 设定类 / 色彩类 | B | `color_design` | 7,637 |
| 14 | 总作画监督 | Chief Animation Director | チーフ作画監督 | 导演类 / 作画类 | A | `chief_animation_director` | 10,861 |
| 15 | 作画监督 | Animation Direction | 作監 アニメーション演出 | 导演类 / 作画类 | B | `animation_director` | 85,918 |
| 16 | 机械设定 | Mechanical Design | メカニック設定 | 设定类 | C | `mechanical_design` | 2,851 |
| 17 | 摄影监督 | Director of Photography | 撮影監督 | 导演类 / 制作类 | B | `photography_director` | 8,577 |
| 18 | 监修 | Supervision/Supervisor | シリーズ監修 スーパーバイザー | 导演类 | B | `supervisor` | 1,586 |
| 19 | 道具设计 | Prop Design | プロップデザイン | 设定类 | C | `prop_design` | 4,087 |
| 20 | 原画 | Key Animation | 作画 原画 | 演出类 / 作画类 | C | `key_animation` | 225,236 |
| 21 | 第二原画 | 2nd Key Animation | 原画協力 | 演出类 / 作画类 | C | `second_key_animation` | 49,433 |
| 22 | 动画检查 | Animation Check | 動画チェック | 演出类 / 作画类 | C | `animation_check` | 6,825 |
| 23 | 助理制片人 | Assistant Producer | 協力プロデューサー（⚠️ 待合并） |  | D | `assistant_producer_legacy` | 686 |
| 24 | 制作助理 | Associate Producer | 製作補佐 アソシエイトプロデューサー | 制作类 / 助理类 | D | `associate_producer_assistant` | 124 |
| 25 | 背景美术 | Background Art | 背景 | 美术类 / 设定类 | C | `background_art` | 8,785 |
| 26 | 色彩指定 | Color Setting |  | 设定类 / 色彩类 | C | `color_setting` | 5,491 |
| 27 | 数码绘图 | Digital Paint |  | 设定类 | D | `digital_paint` | 302 |
| 28 | 剪辑 | Editing | 編集 | 制作类 | B | `editing` | 9,368 |
| 29 | 原案 | Original Plan |  | 分镜/脚本类 | A | `original_plan` | 1,206 |
| 30 | 主题歌编曲 | Theme Song Arrangement |  | 声音类 | C | `theme_song_arrangement` | 5,028 |
| 31 | 主题歌作曲 | Theme Song Composition |  | 声音类 | C | `theme_song_composition` | 5,708 |
| 32 | 主题歌作词 | Theme Song Lyrics |  | 声音类 | C | `theme_song_lyrics` | 5,503 |
| 33 | 主题歌演出 | Theme Song Performance |  | 声音类 | C | `theme_song_performance` | 9,313 |
| 34 | 插入歌演出 | Inserted Song Performance |  | 声音类 | C | `inserted_song_performance` | 1,920 |
| 35 | 企画 | Planning | プランニング  企画開発 | 制作类 | A | `planning` | 14,637 |
| 36 | 企划制作人 | Planning Producer | 企画プロデューサー 企画営業プロデューサー | 制片类 | A | `planning_producer` | 348 |
| 37 | 制作管理 | Production Manager | 制作マネージャー 制作担当 制作班長 | 制作类 | C | `production_manager` | 3,294 |
| 38 | 宣传 | Publicity | パブリシティ  宣伝  広告宣伝  番組宣伝  製作宣伝 | 制作类 | D | `publicity` | 1,195 |
| 39 | 录音 | Recording | 録音 | 声音类 | C | `recording` | 2,816 |
| 40 | 录音助理 | Recording Assistant | 録音アシスタント  録音助手 | 声音类 / 助理类 | D | `recording_assistant` | 795 |
| 41 | 系列监督 | Series Production Director |  | 导演类 | A | `series_production_director` | 465 |
| 42 | 製作 | Production |  | 制作类 | D | `anime_staff_42` | 12,755 |
| 43 | 设定 | Setting | 設定 | 设定类 | C | `setting` | 3,385 |
| 44 | 音响监督 | Sound Director |  | 导演类 / 声音类 | B | `sound_director` | 8,469 |
| 45 | 音响 | Sound | 音響 音声 | 声音类 | C | `sound` | 1,882 |
| 46 | 音效 | Sound Effects | 音響効果 | 声音类 | C | `sound_effects` | 5,824 |
| 47 | 特效 | Special Effects | 特殊効果 | 制作类 / 视觉类 | C | `special_effects` | 3,559 |
| 48 | 配音监督 | ADR Director |  | 声音类 / 导演类 | B | `adr_director` | 1,381 |
| 49 | 联合导演 | Co-Director |  | 导演类 | A | `co_director` | 894 |
| 50 | 背景设定 | Setting | 基本設定  場面設定  場面設計  設定 | 设定类 | C | `background_setting` | 306 |
| 51 | 补间动画 | In-Between Animation | 動画 | 作画类 | D | `in_between_animation` | 27,223 |
| 52 | 执行制片人 | Executive Producer | 製作総指揮 | 制片类 | A | `executive_producer` | 4,699 |
| 53 | 助理制片人 | Assistant Producer | 協力プロデューサー  アシスタントプロデューサー | 制片类 / 助理类 | B | `assistant_producer` | 1,464 |
| 54 | 制片人 | Producer | プロデュース  プロデューサー | 制片类 | A | `producer` | 18,704 |
| 55 | 音乐助理 | Music Assistant | 音楽アシスタント | 声音类 / 助理类 | D | `music_assistant` | 48 |
| 56 | 制作进行 | Assistant Production Manager | 制作進行 | 制作类 | C | `production_assistant` | 7,987 |
| 57 | 演员监督 | Casting Director | キャスティングコーディネーター監督 | 制片类 / 导演类 | C | `casting_director` | 57 |
| 58 | 总制片人 | Chief Producer | チーフプロデューサー チーフ制作 総合プロデューサー | 制片类 | A | `chief_producer` | 3,130 |
| 59 | 联合制片人 | Co-Producer |  | 制片类 | B | `co_producer` | 332 |
| 60 | 台词编辑 | Dialogue Editing | 台詞編集 | 制作类 | D | `dialogue_editing` | 1 |
| 61 | 后期制片协调 | Post-Production Assistant | ポストプロダクション協力 | 制作类 / 助理类 | D | `post_production_assistant` | 5 |
| 62 | 制作助理 | Production Assistant | 制作アシスタント 制作補佐 製作補 | 制作类 / 助理类 | D | `production_assistant_general` | 111 |
| 63 | 制作 | Production | 製作 製作スタジオ | 制作类 | D | `production` | 754 |
| 64 | 制作协调 | Production Coordination | 制作コーディネーター | 制作类 | D | `production_coordination` | 70 |
| 65 | 音乐制作 | Music Work | 楽曲制作 音楽制作 | 声音类 / 制作类 | C | `music_work` | 1,292 |
| 66 | 特别鸣谢 | Special Thanks | 友情協力 | 助理类 | D | `special_thanks` | 1,569 |
| 67 | 动画制作 | Animation Work | アニメーション制作 アニメ制作 アニメーション | 制作类 | C | `animation_work` | 2,062 |
| 69 | CG 导演 | CG Director | CG 監督 | 导演类 / 制作类 | B | `cg_director` | 1,785 |
| 70 | 机械作画监督 | Mechanical Animation Direction | メカニック作監 | 导演类 / 作画类 | B | `mechanical_animation_director` | 1,063 |
| 71 | 美术设计 | Art Design | 美術設定 | 美术类 / 设定类 | B | `art_design` | 5,573 |
| 72 | 副导演 | Assistant Director | 助監督 / 監督補佐 | 导演类 / 助理类 | A | `assistant_director` | 1,853 |
| 73 | OP・ED 分镜 | OP ED | OP・ED 分鏡 | 分镜/脚本类 | B | `op_ed_storyboard` | 5,959 |
| 74 | 总导演 | Chief Director | 総監督 / チーフディレクター | 导演类 | A | `chief_director` | 1,838 |
| 75 | 3DCG | 3DCG |  | 制作类 | C | `3dcg` | 1,982 |
| 76 | 制作协力 | Work Assistance | 制作協力 / 作品協力 | 制作类 / 助理类 | D | `work_assistance` | 3,430 |
| 77 | 动作作画监督 | Action Animation Direction | アクション作画監督 | 导演类 / 作画类 | B | `action_animation_director` | 764 |
| 80 | 监制 | Supervising Producer | プロデュース | 制片类 | A | `supervising_producer` | 3,386 |
| 81 | 协力 | Assistance | 協力 | 助理类 | D | `assistance` | 3,287 |
| 82 | 摄影 | Photography | 撮影 | 制作类 | C | `photography` | 8,101 |
| 83 | 制作进行协力 | Assistant Production Manager Assistance | 制作進行協力 | 制作类 / 助理类 | D | `production_assistant_assistance` | 590 |
| 84 | 设定制作 | Design Manager | 設定制作 制作設定 | 设定类 | C | `setting_production` | 1,499 |
| 85 | 音乐制作人 | Music Producer | 音楽プロデューサー | 声音类 / 制作类 | B | `music_producer` | 2,066 |
| 86 | 3DCG 导演 | 3DCG Director | 3DCG 監督 | 导演类 / 制作类 | B | `3dcg_director` | 710 |
| 87 | 动画制片人 | Animation Producer | アニメプロデューサー  アニメーションプロデューサー | 制片类 | A | `animation_producer` | 4,477 |
| 88 | 特效作画监督 | Special Effects Animation Direction | エフェクト作画監督 | 导演类 / 制作类 / 视觉类 | B | `special_effects_animation_director` | 415 |
| 89 | 主演出 | Chief Episode Direction | チーフ演出 | 演出类 | B | `chief_episode_direction` | 218 |
| 90 | 作画监督助理 | Assistant Animation Direction | 作画監督補佐 | 助理类 / 作画类 | C | `assistant_animation_director` | 7,158 |
| 91 | 演出助理 | Assistant Episode Direction | 演出助手 演出補佐 演出協力 | 演出类 / 助理类 | C | `assistant_episode_director` | 2,410 |
| 92 | 主动画师 | Main Animator | メインアニメーター | 演出类 / 作画类 | B | `main_animator` | 1,175 |
| 93 | 上色 |  | 仕上 | 色彩类 | C | `finishing` | 2,997 |
| 94 | 上色检查 |  | 仕上検查 | 色彩类 | C | `finishing_check` | 805 |
| 95 | 色彩检查 |  | 色検查 | 色彩类 | C | `color_check` | 963 |
| 96 | 美术板 |  | 美術ボード | 美术类 | C | `art_board` | 172 |
| 97 | 美术 |  | 美術 | 美术类 | C | `art` | 503 |
| 98 | 印象板 |  | イメージボード | 美术类 / 设定类 | C | `image_board` | 102 |
| 99 | 2D 设计 | 2D WORKS | 2D ワークス | 设定类 | C | `2d_works` | 498 |
| 100 | 3D 设计 | 3D WORKS | 3D ワークス | 设定类 | C | `3d_works` | 20 |
| 101 | 技术导演 | Technical Director | テクニカルディレクター | 导演类 / 制作类 | B | `technical_director` | 78 |
| 102 | 特技导演 |  | 特撮監督 | 导演类 / 制作类 | B | `tokusatsu_director` | 20 |
| 103 | 色彩脚本 | Color Script | カラースクリプト | 色彩类 | C | `color_script` | 58 |
| 104 | 分镜协力 |  | 絵コンテ協力 コンテ協力 | 分镜/脚本类 / 助理类 | C | `storyboard_cooperation` | 187 |
| 105 | 分镜抄写 |  | 絵コンテ清書 コンテ清書 | 分镜/脚本类 / 助理类 | D | `storyboard_clean_up` | 28 |
| 106 | 副人物设定 | Sub-Character Design | サブキャラクターデザイン | 设定类 | B | `sub_character_design` | 1,520 |
| 107 | 客座人物设定 | Guest character design | ゲストキャラクターデザイン | 设定类 | C | `guest_character_design` | 148 |
| 108 | 构图监修 |  | レイアウト監修 | 演出类 | C | `layout_supervision` | 101 |
| 109 | 构图作画监督 |  | レイアウト作画監督 レイアウト作監 | 导演类 / 作画类 | C | `layout_animation_director` | 73 |
| 110 | 总作画监督助理 |  | 総作画監督補佐 総作監補佐 | 助理类 / 作画类 | C | `assistant_chief_animation_director` | 395 |
| 111 | 道具作画监督 |  | プロップ作画監督 プロップ作監 | 导演类 / 作画类 | C | `prop_animation_director` | 61 |
| 112 | 概念设计 | Concept Design | コンセプトデザイン | 设定类 | C | `concept_design` | 133 |
| 113 | 服装设计 | Costume Design | 衣装デザイン 衣装設定 | 设定类 | C | `costume_design` | 301 |
| 114 | 标题设计 | Title Design | タイトルデザイン | 设定类 | C | `title_design` | 43 |
| 115 | 设定协力 | Setting Cooperation | 設定協力 デザイン協力 | 设定类 / 助理类 | C | `setting_cooperation` | 288 |
| 116 | 音乐监督 | Music Director | 音楽ディレクター | 声音类 / 导演类 | B | `music_director` | 678 |
| 117 | 选曲 | Music Selection | 選曲 | 声音类 | C | `music_selection` | 256 |
| 118 | 插入歌作词 | Inserted Song Lyrics | Insert Song Lyrics | 声音类 | C | `inserted_song_lyrics` | 415 |
| 119 | 插入歌作曲 | Inserted Song Composition | Insert Song Composition | 声音类 | C | `inserted_song_composition` | 460 |
| 120 | 插入歌编曲 | Inserted Song Arrangement | Insert Song Arrangement | 声音类 | C | `inserted_song_arrangement` | 383 |
| 121 | 创意制片人 | Creative Producer | クリエイティブプロデューサー | 制片类 | A | `creative_producer` | 36 |
| 122 | 副制片人 | Associate Producer | アソシエイトプロデューサー | 制片类 / 助理类 | B | `associate_producer` | 718 |
| 123 | 制作统括 | Chief Production Supervisor | 制作統括 | 制作类 | A | `chief_production_supervisor` | 468 |
| 124 | 现场制片人 | Line Producer | ラインプロデューサー | 制片类 / 制作类 | B | `line_producer` | 110 |
| 125 | 文艺制作 | Literary Producer | 文芸制作 | 制片类 | C | `literary_producer` | 145 |
| 127 | 企画协力 | Planning Cooperation | 企画協力 | 制片类 / 助理类 | D | `planning_cooperation` | 834 |
| 128 | OP・ED 演出 | OP・ED Direction | OP・ED 演出 | 演出类 | B | `op_ed_direction` | 1,870 |
| 129 | Bank 分镜演出 | Bank Storyboard Direction | バンク コンテ・演出 | 演出类 | C | `bank_storyboard_direction` | 66 |
| 130 | Live 分镜演出 | Live Storyboard Direction | ライブ コンテ・演出 | 演出类 | C | `live_storyboard_direction` | 154 |
| 131 | 剧中剧分镜演出 | Meta-story Storyboard Direction | 劇中劇 コンテ・演出 | 演出类 | C | `meta_story_storyboard_direction` | 13 |
| 132 | 剧中剧人设 | Meta-story Character Design | 劇中劇 キャラクターデザイン | 设定类 | C | `meta_story_character_design` | 17 |
| 133 | 视觉导演 | Visual Director | ビジュアルディレクター | 视觉类 / 导演类 | B | `visual_director` | 51 |
| 134 | 创意总监 | Creative Supervisor/Director | クリエイティブスーパーバイザー クリエイティブディレクター | 导演类 | B | `creative_supervisor_director` | 45 |
| 135 | 特摄效果 | Tokusatsu Effects | 特撮 | 制作类 / 视觉类 | C | `tokusatsu_effects` | 18 |
| 136 | 视觉效果 | Visual Effects | ビジュアルエフェクト | 视觉类 | C | `visual_effects` | 164 |
| 137 | 动作导演 |  | アクション監督 | 导演类 / 制作类 | B | `action_director` | 104 |
| 138 | 转场绘 | Eyecatch Art | アイキャッチ | 作画类 / 视觉类 | C | `eyecatch_art` | 105 |
| 139 | 插画 | Illustration | イラスト | 作画类 / 设定类 | C | `illustration` | 1,773 |
| 140 | 角色作画监督 | Character Animation Director | キャラクター作画監督 | 导演类 / 作画类 | B | `character_animation_director` | 95 |
| 141 | 作画监修 | Animation Supervisor | 作画監修 | 导演类 / 作画类 | B | `animation_supervisor` | 79 |
| 142 | 机设原案 | Mechanical Design Concept | メカニカル原案 | 设定类 | C | `mechanical_design_concept` | 17 |
| 143 | 概念艺术 | Concept Art | コンセプトアート | 设定类 | C | `concept_art` | 60 |
| 144 | 视觉概念 | Visual Concept | ビジュアルコンセプト | 设定类 / 视觉类 | C | `visual_concept` | 23 |
| 145 | 画面设计 | Scene Design | 画面設計 | 设定类 / 视觉类 | C | `scene_design` | 25 |
| 146 | 怪物设计 | Monster Design | モンスターデザイン | 设定类 | C | `monster_design` | 190 |
| 147 | 故事概念 | Story Concept | ストーリーコンセプト | 分镜/脚本类 | C | `story_concept` | 5 |
| 148 | 剧本协调 | Scenario Coordinator | シナリオコーディネーター | 分镜/脚本类 | C | `scenario_coordinator` | 1 |
| 149 | 脚本协力 | Script Cooperation | 脚本協力 | 分镜/脚本类 / 助理类 | C | `script_cooperation` | 141 |
| 150 | 副系列构成 | Associate Series Composition | 副シリーズ構成 | 分镜/脚本类 | B | `associate_series_composition` | 10 |
| 151 | 构成协力 | Series Composition Cooperation | 構成協力 | 分镜/脚本类 / 助理类 | C | `series_composition_cooperation` | 28 |
| 152 | 录音工作室 | Recording Studio | 録音スタジオ | 声音类 / 制作类 | D | `recording_studio` | 236 |
| 153 | 整音 | Sound Mixing | 整音 | 声音类 | C | `sound_mixing` | 36 |
| 154 | 音响制作担当 | Sound Production Coordinator | 音響制作担当 | 声音类 / 制作类 | C | `sound_production_coordinator` | 565 |
| 155 | 在线剪辑 | Online Editing | オンライン編集 | 制作类 | C | `online_editing` | 33 |
| 156 | 离线剪辑 | Offline Editing | オフライン編集 | 制作类 | C | `offline_editing` | 31 |
| 157 | 3D 动画师 | 3D Animator | 3Dアニメーター  3Dアニメーション | 制作类 / 作画类 | C | `3d_animator` | 81 |
| 158 | CG 制作人 | CG Producer | CGプロデューサー  CGIプロデューサー | 制片类 / 制作类 | B | `cg_producer` | 109 |
| 159 | 宣传制片人 | Publicity Producer | 宣伝プロデューサー | 制片类 / 制作类 | B | `publicity_producer` | 88 |
| 160 | 美术制作人 | Art Producer | 美術プロデューサー | 制片类 / 美术类 | B | `art_producer` | 4 |
| 161 | 音响制作人 | Sound Producer | 音響プロデューサー | 制片类 / 声音类 | B | `sound_producer` | 39 |
| 162 | CG 制作进行 | CG Production Coordinator | CG進行 | 制片类 / 制作类 | C | `cg_production_coordinator` | 37 |
| 163 | 美术制作进行 | Art Production Coordinator | 美術進行 | 制片类 / 美术类 / 制作类 | C | `art_production_coordinator` | 11 |
| 164 | 美术监督助理 | Assistant Art Director | 美術監督補佐 | 助理类 / 美术类 | B | `assistant_art_director` | 170 |
| 165 | 色彩设计助理 | Assistant Color Designer | 色彩設計補佐 | 助理类 / 色彩类 | C | `assistant_color_designer` | 140 |
| 166 | 摄影监督助理 | Assistant Director of Photography | 撮影監督補佐 | 助理类 / 制作类 | B | `assistant_photography_director` | 259 |
| 167 | 制作管理助理 | Assistant Production Desk | 制作デスク補佐 | 助理类 / 制作类 | C | `assistant_production_desk` | 45 |
| 168 | 设定制作助理 | Assistant Design Manager | 設定制作補佐 | 助理类 / 设定类 | C | `assistant_design_manager` | 16 |

## Non-Anime Staff Constants For Reference

以下仅供参考，本项目当前不处理非动画条目。

### 1 book 书籍

| Position ID | CN | EN | JP |
| ---: | --- | --- | --- |
| 2001 | 作者 |  |  |
| 2002 | 作画 |  |  |
| 2003 | 插图 |  | イラスト |
| 2004 | 出版社 |  |  |
| 2005 | 连载杂志 |  | 掲載誌 |
| 2006 | 译者 |  |  |
| 2007 | 原作 | Original Creator/Original Work |  |
| 2008 | 客串 | Guest | ゲスト |
| 2009 | 人物原案 | Original Character Design | キャラクター原案 |
| 2010 | 脚本 |  | シナリオ |
| 2011 | 书系 | Label |  |
| 2012 | 出品方 |  |  |
| 2013 | 图书品牌 | Brand | ブランド |

### 3 music 音乐

| Position ID | CN | EN | JP |
| ---: | --- | --- | --- |
| 3001 | 艺术家 | Artist |  |
| 3002 | 制作人 | Producer |  |
| 3003 | 作曲 | Composer |  |
| 3004 | 厂牌 | Label | レーベル |
| 3005 | 原作 | Original Creator/Original Work |  |
| 3006 | 作词 | Lyric |  |
| 3007 | 录音 | Recording |  |
| 3008 | 编曲 | Arrange |  |
| 3009 | 插图 | Illustrator |  |
| 3010 | 脚本 | Scenario | シナリオ |
| 3011 | 出版方 | O.P. | 音楽出版社 |
| 3012 | 母带制作 | Mastering |  |
| 3013 | 混音 | Mixing |  |
| 3014 | 乐器 | Instrument |  |
| 3015 | 声乐 | Vocal |  |

### 4 game 游戏

| Position ID | CN | EN | JP |
| ---: | --- | --- | --- |
| 1001 | 开发 | Developer | 開発元 |
| 1002 | 发行 | Publisher | 発売元 |
| 1003 | 游戏设计师 | Game Designer | ゲームクリエイター |
| 1004 | 剧本 |  | 腳本 |
| 1005 | 美工 |  | 美術 |
| 1006 | 音乐 |  | 音楽 |
| 1007 | 关卡设计 |  |  |
| 1008 | 人物设定 | Character Design | キャラ設定 キャラクターデザイン |
| 1009 | 主题歌作曲 | Theme Song Composition |  |
| 1010 | 主题歌作词 | Theme Song Lyrics |  |
| 1011 | 主题歌演出 | Theme Song Performance |  |
| 1012 | 插入歌演出 | Inserted Song Performance |  |
| 1013 | 原画 |  |  |
| 1014 | 动画制作 | Animation Work | アニメーション制作 アニメ制作 アニメーション |
| 1015 | 原作 |  |  |
| 1016 | 导演 | Director/Direction | 監督 演出 シリーズ監督 |
| 1017 | 动画监督 |  | アニメーション監督 |
| 1018 | 制作总指挥 |  |  |
| 1019 | QC | QC |  |
| 1020 | 动画剧本 |  | アニメーション脚本 |
| 1021 | 程序 | Program | プログラム |
| 1022 | 协力 |  | 協力 |
| 1023 | CG 监修 |  | CG 監修 |
| 1024 | SD原画 |  |  |
| 1025 | 背景 |  |  |
| 1026 | 监修 |  | 監修 |
| 1027 | 系列构成 |  | シリーズ構成 |
| 1028 | 企画 |  |  |
| 1029 | 机械设定 | Mechanical Design | メカニック設定 |
| 1030 | 音响监督 | Sound Director |  |
| 1031 | 作画监督 |  | 作画監督 |
| 1032 | 制作人 | Producer | プロデューサー |
| 1033 | 海报 | Cover Art | 表紙 |

### 6 real 三次元

| Position ID | CN | EN | JP |
| ---: | --- | --- | --- |
| 4001 | 原作 | Creator |  |
| 4002 | 导演 | Director |  |
| 4003 | 编剧 | Writer |  |
| 4004 | 音乐 | Composer |  |
| 4005 | 执行制片人 | Executive Producer | 製作総指揮 |
| 4006 | 共同执行制作 | Co-Executive Producer |  |
| 4007 | 制片人/制作人 | Producer | プロデューサー |
| 4008 | 监制 | Supervising Producer |  |
| 4009 | 副制作人/制作顾问 | Consulting Producer |  |
| 4010 | 故事 | Story |  |
| 4011 | 编审 | Story Editor |  |
| 4012 | 剪辑 | Editor |  |
| 4013 | 创意总监 | Creative Director |  |
| 4014 | 摄影 | Cinematography |  |
| 4015 | 主题歌演出 | Theme Song Performance |  |
| 4016 | 主演 | Actor |  |
| 4017 | 配角 | Supporting Actor |  |
| 4018 | 制作 | Production | 製作 製作スタジオ |
| 4019 | 出品 | Present | 配給 |
| 4020 | 配音导演 | ADR Director |  |
| 4021 | 录音 | Recording | 録音 |
| 4022 | 海报 | Poster |  |
