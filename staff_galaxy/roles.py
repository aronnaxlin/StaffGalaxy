from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class StaffPosition:
    position_id: int
    cn: str
    en: str
    jp: str


@dataclass(frozen=True)
class RoleDefinition:
    position_id: int
    normalized_role: str
    role_tier: str
    role_weight: float


ROLE_DEFINITIONS: dict[int, RoleDefinition] = {}


def _set_role(position_id: int, normalized_role: str, role_tier: str, role_weight: float) -> None:
    ROLE_DEFINITIONS[position_id] = RoleDefinition(
        position_id, normalized_role, role_tier, role_weight
    )


# ── Weight scale (exponential, additive scoring via SQRT(w1 * w2)) ──
# S:  50.0  — Soul of the work / top decision-makers
# A:  25.0  — Creative core that defines the work's identity
# B:  12.0  — Key creative roles shaping major aspects
# C:   6.0  — Technical leads and department heads
# D:   3.0  — Skilled hands-on production
# E:   1.0  — Support and assistant roles
# F:   0.3  — Minimal or indirect involvement

# ── Tier S: 导演 / 总导演 ──
_set_role(2, "director", "S", 50.0)
_set_role(74, "chief_director", "S", 50.0)

# ── Tier A: Creative core ──
_set_role(1, "original_creator", "A", 25.0)
_set_role(10, "series_composition", "A", 25.0)
_set_role(8, "character_design", "A", 25.0)
_set_role(14, "chief_animation_director", "A", 25.0)
_set_role(87, "animation_producer", "A", 25.0)
_set_role(72, "assistant_director", "A", 25.0)
_set_role(49, "co_director", "A", 25.0)

# ── Tier B: Key creative ──
_set_role(3, "script", "B", 12.0)
_set_role(6, "music", "B", 12.0)
_set_role(4, "storyboard", "B", 12.0)
_set_role(5, "episode_director", "B", 12.0)
_set_role(7, "original_character_design", "B", 12.0)
_set_role(54, "producer", "B", 12.0)
_set_role(58, "chief_producer", "B", 12.0)
_set_role(52, "executive_producer", "B", 12.0)
_set_role(41, "series_production_director", "B", 12.0)
_set_role(35, "planning", "B", 12.0)
_set_role(36, "planning_producer", "B", 12.0)
_set_role(29, "original_plan", "B", 12.0)
_set_role(80, "supervising_producer", "B", 12.0)
_set_role(121, "creative_producer", "B", 12.0)
_set_role(123, "chief_production_supervisor", "B", 12.0)

# ── Tier C: Technical leads / department heads ──
_set_role(11, "art_director", "C", 6.0)
_set_role(17, "photography_director", "C", 6.0)
_set_role(44, "sound_director", "C", 6.0)
_set_role(13, "color_design", "C", 6.0)
_set_role(28, "editing", "C", 6.0)
_set_role(86, "3dcg_director", "C", 6.0)
_set_role(69, "cg_director", "C", 6.0)
_set_role(15, "animation_director", "C", 6.0)
_set_role(92, "main_animator", "C", 6.0)
_set_role(89, "chief_episode_direction", "C", 6.0)
_set_role(77, "action_animation_director", "C", 6.0)
_set_role(88, "special_effects_animation_director", "C", 6.0)
_set_role(70, "mechanical_animation_director", "C", 6.0)
_set_role(140, "character_animation_director", "C", 6.0)
_set_role(18, "supervisor", "C", 6.0)
_set_role(141, "animation_supervisor", "C", 6.0)
_set_role(116, "music_director", "C", 6.0)
_set_role(101, "technical_director", "C", 6.0)
_set_role(102, "tokusatsu_director", "C", 6.0)
_set_role(133, "visual_director", "C", 6.0)
_set_role(134, "creative_supervisor_director", "C", 6.0)
_set_role(137, "action_director", "C", 6.0)
_set_role(106, "sub_character_design", "C", 6.0)
_set_role(71, "art_design", "C", 6.0)
_set_role(48, "adr_director", "C", 6.0)
_set_role(73, "op_ed_storyboard", "C", 6.0)
_set_role(128, "op_ed_direction", "C", 6.0)
_set_role(150, "associate_series_composition", "C", 6.0)
_set_role(53, "assistant_producer", "C", 6.0)
_set_role(59, "co_producer", "C", 6.0)
_set_role(122, "associate_producer", "C", 6.0)
_set_role(124, "line_producer", "C", 6.0)
_set_role(85, "music_producer", "C", 6.0)
_set_role(158, "cg_producer", "C", 6.0)
_set_role(159, "publicity_producer", "C", 6.0)
_set_role(160, "art_producer", "C", 6.0)
_set_role(161, "sound_producer", "C", 6.0)
_set_role(164, "assistant_art_director", "C", 6.0)
_set_role(166, "assistant_photography_director", "C", 6.0)

# ── Tier D: Skilled production ──
_set_role(20, "key_animation", "D", 3.0)
_set_role(16, "mechanical_design", "D", 3.0)
_set_role(19, "prop_design", "D", 3.0)
_set_role(9, "layout", "D", 3.0)
_set_role(21, "second_key_animation", "D", 3.0)
_set_role(22, "animation_check", "D", 3.0)
_set_role(25, "background_art", "D", 3.0)
_set_role(26, "color_setting", "D", 3.0)
_set_role(93, "finishing", "D", 3.0)
_set_role(94, "finishing_check", "D", 3.0)
_set_role(95, "color_check", "D", 3.0)
_set_role(82, "photography", "D", 3.0)
_set_role(75, "3dcg", "D", 3.0)
_set_role(157, "3d_animator", "D", 3.0)
_set_role(67, "animation_work", "D", 3.0)
_set_role(84, "setting_production", "D", 3.0)
_set_role(37, "production_manager", "D", 3.0)
_set_role(65, "music_work", "D", 3.0)
_set_role(31, "theme_song_composition", "D", 3.0)
_set_role(32, "theme_song_lyrics", "D", 3.0)
_set_role(30, "theme_song_arrangement", "D", 3.0)
_set_role(33, "theme_song_performance", "D", 3.0)
_set_role(34, "inserted_song_performance", "D", 3.0)
_set_role(118, "inserted_song_lyrics", "D", 3.0)
_set_role(119, "inserted_song_composition", "D", 3.0)
_set_role(120, "inserted_song_arrangement", "D", 3.0)
_set_role(117, "music_selection", "D", 3.0)
_set_role(39, "recording", "D", 3.0)
_set_role(46, "sound_effects", "D", 3.0)
_set_role(45, "sound", "D", 3.0)
_set_role(47, "special_effects", "D", 3.0)
_set_role(135, "tokusatsu_effects", "D", 3.0)
_set_role(136, "visual_effects", "D", 3.0)
_set_role(112, "concept_design", "D", 3.0)
_set_role(113, "costume_design", "D", 3.0)
_set_role(114, "title_design", "D", 3.0)
_set_role(96, "art_board", "D", 3.0)
_set_role(97, "art", "D", 3.0)
_set_role(98, "image_board", "D", 3.0)
_set_role(99, "2d_works", "D", 3.0)
_set_role(100, "3d_works", "D", 3.0)
_set_role(103, "color_script", "D", 3.0)
_set_role(145, "scene_design", "D", 3.0)
_set_role(146, "monster_design", "D", 3.0)
_set_role(142, "mechanical_design_concept", "D", 3.0)
_set_role(143, "concept_art", "D", 3.0)
_set_role(147, "story_concept", "D", 3.0)
_set_role(144, "visual_concept", "D", 3.0)
_set_role(139, "illustration", "D", 3.0)
_set_role(138, "eyecatch_art", "D", 3.0)
_set_role(50, "background_setting", "D", 3.0)
_set_role(43, "setting", "D", 3.0)
_set_role(108, "layout_supervision", "D", 3.0)
_set_role(109, "layout_animation_director", "D", 3.0)
_set_role(111, "prop_animation_director", "D", 3.0)
_set_role(90, "assistant_animation_director", "D", 3.0)
_set_role(91, "assistant_episode_director", "D", 3.0)
_set_role(110, "assistant_chief_animation_director", "D", 3.0)
_set_role(107, "guest_character_design", "D", 3.0)
_set_role(115, "setting_cooperation", "D", 3.0)
_set_role(104, "storyboard_cooperation", "D", 3.0)
_set_role(149, "script_cooperation", "D", 3.0)
_set_role(151, "series_composition_cooperation", "D", 3.0)
_set_role(125, "literary_producer", "D", 3.0)
_set_role(57, "casting_director", "D", 3.0)
_set_role(148, "scenario_coordinator", "D", 3.0)
_set_role(167, "assistant_production_desk", "D", 3.0)
_set_role(168, "assistant_design_manager", "D", 3.0)
_set_role(165, "assistant_color_designer", "D", 3.0)
_set_role(163, "art_production_coordinator", "D", 3.0)
_set_role(162, "cg_production_coordinator", "D", 3.0)
_set_role(154, "sound_production_coordinator", "D", 3.0)
_set_role(156, "offline_editing", "D", 3.0)
_set_role(155, "online_editing", "D", 3.0)
_set_role(153, "sound_mixing", "D", 3.0)
_set_role(129, "bank_storyboard_direction", "D", 3.0)
_set_role(130, "live_storyboard_direction", "D", 3.0)
_set_role(131, "meta_story_storyboard_direction", "D", 3.0)
_set_role(132, "meta_story_character_design", "D", 3.0)

# ── Tier E: Support / assistant ──
_set_role(56, "production_assistant", "E", 1.0)
_set_role(51, "in_between_animation", "E", 1.0)
_set_role(27, "digital_paint", "E", 1.0)
_set_role(83, "production_assistant_assistance", "E", 1.0)
_set_role(62, "production_assistant_general", "E", 1.0)
_set_role(24, "associate_producer_assistant", "E", 1.0)
_set_role(23, "assistant_producer_legacy", "E", 1.0)
_set_role(64, "production_coordination", "E", 1.0)
_set_role(61, "post_production_assistant", "E", 1.0)
_set_role(60, "dialogue_editing", "E", 1.0)
_set_role(38, "publicity", "E", 1.0)
_set_role(40, "recording_assistant", "E", 1.0)
_set_role(55, "music_assistant", "E", 1.0)
_set_role(105, "storyboard_clean_up", "E", 1.0)
_set_role(127, "planning_cooperation", "E", 1.0)

# ── Tier F: Minimal / indirect ──
_set_role(66, "special_thanks", "F", 0.3)
_set_role(81, "assistance", "F", 0.3)
_set_role(42, "anime_staff_42", "F", 0.3)  # 製作
_set_role(63, "production", "F", 0.3)
_set_role(76, "work_assistance", "F", 0.3)
_set_role(152, "recording_studio", "F", 0.3)


def detect_staff_constants(raw_dir: Path, explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        if not explicit_path.exists():
            raise FileNotFoundError(f"subject_staffs.yml does not exist: {explicit_path}")
        return explicit_path

    candidate = raw_dir / "bangumi-common" / "subject_staffs.yml"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"Could not find subject_staffs.yml under {raw_dir / 'bangumi-common'}. "
        "Clone https://github.com/bangumi/common or pass --staffs-yml."
    )


def load_anime_staff_positions(path: Path) -> dict[int, StaffPosition]:
    payload: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        anime_staffs = payload["staffs"][2]
    except KeyError as exc:
        raise ValueError(f"{path} does not contain staffs[2] anime staff mappings") from exc

    positions: dict[int, StaffPosition] = {}
    for raw_id, meta in anime_staffs.items():
        position_id = int(raw_id)
        positions[position_id] = StaffPosition(
            position_id=position_id,
            cn=str(meta.get("cn") or ""),
            en=str(meta.get("en") or ""),
            jp=str(meta.get("jp") or ""),
        )
    return positions


def role_definition_for(position: StaffPosition) -> RoleDefinition:
    explicit = ROLE_DEFINITIONS.get(position.position_id)
    if explicit is not None:
        return explicit
    return RoleDefinition(
        position_id=position.position_id,
        normalized_role=f"anime_staff_{position.position_id}",
        role_tier="E",
        role_weight=1.0,
    )
