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


EXPLICIT_ROLE_DEFINITIONS: dict[int, RoleDefinition] = {
    2: RoleDefinition(2, "director", "A", 10.0),
    74: RoleDefinition(74, "director", "A", 10.0),
    72: RoleDefinition(72, "assistant_director", "A", 8.0),
    10: RoleDefinition(10, "series_composition", "A", 8.0),
    8: RoleDefinition(8, "character_design", "A", 7.0),
    14: RoleDefinition(14, "chief_animation_director", "A", 7.0),
    87: RoleDefinition(87, "animation_producer", "A", 8.0),
    54: RoleDefinition(54, "producer", "A", 6.0),
    6: RoleDefinition(6, "music", "A", 5.0),
    1: RoleDefinition(1, "original_creator", "B", 4.0),
    7: RoleDefinition(7, "original_character_design", "B", 4.0),
    13: RoleDefinition(13, "color_design", "B", 3.0),
    18: RoleDefinition(18, "supervisor", "B", 4.0),
    28: RoleDefinition(28, "editing", "B", 3.0),
    29: RoleDefinition(29, "original_plan", "B", 4.0),
    49: RoleDefinition(49, "co_director", "B", 5.0),
    52: RoleDefinition(52, "executive_producer", "B", 4.0),
    58: RoleDefinition(58, "chief_producer", "B", 4.0),
    71: RoleDefinition(71, "art_design", "B", 3.0),
    80: RoleDefinition(80, "supervising_producer", "B", 4.0),
    4: RoleDefinition(4, "storyboard", "B", 4.0),
    5: RoleDefinition(5, "episode_director", "B", 4.0),
    3: RoleDefinition(3, "script", "B", 4.0),
    15: RoleDefinition(15, "animation_director", "B", 3.0),
    11: RoleDefinition(11, "art_director", "B", 3.0),
    17: RoleDefinition(17, "photography_director", "B", 3.0),
    44: RoleDefinition(44, "sound_director", "B", 3.0),
    20: RoleDefinition(20, "key_animation", "C", 1.0),
    21: RoleDefinition(21, "second_key_animation", "C", 1.0),
    56: RoleDefinition(56, "production_assistant", "C", 1.0),
    84: RoleDefinition(84, "setting_production", "C", 1.0),
    9: RoleDefinition(9, "layout", "C", 1.0),
    16: RoleDefinition(16, "mechanical_design", "C", 1.0),
    19: RoleDefinition(19, "prop_design", "C", 1.0),
    22: RoleDefinition(22, "animation_check", "C", 1.0),
    25: RoleDefinition(25, "background_art", "C", 1.0),
    26: RoleDefinition(26, "color_setting", "C", 1.0),
    30: RoleDefinition(30, "theme_song_arrangement", "C", 1.0),
    31: RoleDefinition(31, "theme_song_composition", "C", 1.0),
    32: RoleDefinition(32, "theme_song_lyrics", "C", 1.0),
    33: RoleDefinition(33, "theme_song_performance", "C", 1.0),
    34: RoleDefinition(34, "inserted_song_performance", "C", 1.0),
    35: RoleDefinition(35, "planning", "C", 1.0),
    37: RoleDefinition(37, "production_manager", "C", 1.0),
    39: RoleDefinition(39, "recording", "C", 1.0),
    46: RoleDefinition(46, "sound_effects", "C", 1.0),
    48: RoleDefinition(48, "adr_director", "C", 1.0),
    51: RoleDefinition(51, "in_between_animation", "D", 0.25),
    69: RoleDefinition(69, "cg_director", "C", 1.0),
    70: RoleDefinition(70, "mechanical_animation_director", "C", 1.0),
    73: RoleDefinition(73, "op_ed_storyboard", "C", 1.0),
    82: RoleDefinition(82, "photography", "C", 1.0),
    85: RoleDefinition(85, "music_producer", "C", 1.0),
    86: RoleDefinition(86, "3dcg_director", "C", 1.0),
    88: RoleDefinition(88, "special_effects_animation_director", "C", 1.0),
    90: RoleDefinition(90, "assistant_animation_director", "C", 1.0),
    91: RoleDefinition(91, "assistant_episode_director", "C", 1.0),
    92: RoleDefinition(92, "main_animator", "C", 1.0),
    106: RoleDefinition(106, "sub_character_design", "C", 1.0),
    109: RoleDefinition(109, "layout_animation_director", "C", 1.0),
    110: RoleDefinition(110, "assistant_chief_animation_director", "C", 1.0),
    111: RoleDefinition(111, "prop_animation_director", "C", 1.0),
    116: RoleDefinition(116, "music_director", "C", 1.0),
    128: RoleDefinition(128, "op_ed_direction", "C", 1.0),
    137: RoleDefinition(137, "action_director", "C", 1.0),
    140: RoleDefinition(140, "character_animation_director", "C", 1.0),
    141: RoleDefinition(141, "animation_supervisor", "C", 1.0),
    150: RoleDefinition(150, "associate_series_composition", "C", 1.0),
    164: RoleDefinition(164, "assistant_art_director", "C", 1.0),
    166: RoleDefinition(166, "assistant_photography_director", "C", 1.0),
}


ROLE_DEFINITIONS: dict[int, RoleDefinition] = dict(EXPLICIT_ROLE_DEFINITIONS)


def _set_role(position_id: int, normalized_role: str, role_tier: str, role_weight: float) -> None:
    ROLE_DEFINITIONS[position_id] = RoleDefinition(
        position_id, normalized_role, role_tier, role_weight
    )


# Manual Staff Galaxy review pass for anime-only staff positions.
# Tier A: default global backbone candidates.
_set_role(1, "original_creator", "A", 9.0)
_set_role(2, "director", "A", 10.0)
_set_role(6, "music", "A", 5.0)
_set_role(7, "original_character_design", "A", 6.0)
_set_role(8, "character_design", "A", 7.0)
_set_role(10, "series_composition", "A", 8.0)
_set_role(14, "chief_animation_director", "A", 7.0)
_set_role(29, "original_plan", "A", 6.0)
_set_role(35, "planning", "A", 6.0)
_set_role(36, "planning_producer", "A", 6.0)
_set_role(41, "series_production_director", "A", 8.0)
_set_role(49, "co_director", "A", 8.0)
_set_role(52, "executive_producer", "A", 6.0)
_set_role(54, "producer", "A", 6.0)
_set_role(58, "chief_producer", "A", 6.0)
_set_role(72, "assistant_director", "A", 8.0)
_set_role(74, "chief_director", "A", 10.0)
_set_role(80, "supervising_producer", "A", 6.0)
_set_role(87, "animation_producer", "A", 8.0)
_set_role(121, "creative_producer", "A", 6.0)
_set_role(123, "chief_production_supervisor", "A", 5.0)

# Tier B: important local expansion and prominent detail roles.
_set_role(3, "script", "B", 4.0)
_set_role(4, "storyboard", "B", 4.0)
_set_role(5, "episode_director", "B", 4.0)
_set_role(11, "art_director", "B", 3.0)
_set_role(13, "color_design", "B", 3.0)
_set_role(15, "animation_director", "B", 3.0)
_set_role(17, "photography_director", "B", 3.0)
_set_role(18, "supervisor", "B", 4.0)
_set_role(28, "editing", "B", 3.0)
_set_role(44, "sound_director", "B", 3.0)
_set_role(48, "adr_director", "B", 3.0)
_set_role(53, "assistant_producer", "B", 3.0)
_set_role(59, "co_producer", "B", 3.0)
_set_role(69, "cg_director", "B", 3.0)
_set_role(70, "mechanical_animation_director", "B", 3.0)
_set_role(71, "art_design", "B", 3.0)
_set_role(73, "op_ed_storyboard", "B", 3.0)
_set_role(77, "action_animation_director", "B", 3.0)
_set_role(85, "music_producer", "B", 3.0)
_set_role(86, "3dcg_director", "B", 3.0)
_set_role(88, "special_effects_animation_director", "B", 3.0)
_set_role(89, "chief_episode_direction", "B", 3.0)
_set_role(92, "main_animator", "B", 3.0)
_set_role(101, "technical_director", "B", 3.0)
_set_role(102, "tokusatsu_director", "B", 3.0)
_set_role(106, "sub_character_design", "B", 3.0)
_set_role(116, "music_director", "B", 3.0)
_set_role(122, "associate_producer", "B", 3.0)
_set_role(124, "line_producer", "B", 3.0)
_set_role(128, "op_ed_direction", "B", 3.0)
_set_role(133, "visual_director", "B", 3.0)
_set_role(134, "creative_supervisor_director", "B", 3.0)
_set_role(137, "action_director", "B", 3.0)
_set_role(140, "character_animation_director", "B", 3.0)
_set_role(141, "animation_supervisor", "B", 3.0)
_set_role(150, "associate_series_composition", "B", 3.0)
_set_role(158, "cg_producer", "B", 3.0)
_set_role(159, "publicity_producer", "B", 3.0)
_set_role(160, "art_producer", "B", 3.0)
_set_role(161, "sound_producer", "B", 3.0)
_set_role(164, "assistant_art_director", "B", 3.0)
_set_role(166, "assistant_photography_director", "B", 3.0)

# Tier C: normal person detail roles, but not global backbone roles.
_set_role(9, "layout", "C", 1.0)
_set_role(16, "mechanical_design", "C", 1.0)
_set_role(19, "prop_design", "C", 1.0)
_set_role(20, "key_animation", "C", 1.0)
_set_role(21, "second_key_animation", "C", 1.0)
_set_role(22, "animation_check", "C", 1.0)
_set_role(25, "background_art", "C", 1.0)
_set_role(26, "color_setting", "C", 1.0)
_set_role(30, "theme_song_arrangement", "C", 1.0)
_set_role(31, "theme_song_composition", "C", 1.0)
_set_role(32, "theme_song_lyrics", "C", 1.0)
_set_role(33, "theme_song_performance", "C", 1.0)
_set_role(34, "inserted_song_performance", "C", 1.0)
_set_role(37, "production_manager", "C", 1.0)
_set_role(39, "recording", "C", 1.0)
_set_role(43, "setting", "C", 1.0)
_set_role(45, "sound", "C", 1.0)
_set_role(46, "sound_effects", "C", 1.0)
_set_role(47, "special_effects", "C", 1.0)
_set_role(50, "background_setting", "C", 1.0)
_set_role(56, "production_assistant", "C", 1.0)
_set_role(57, "casting_director", "C", 1.0)
_set_role(65, "music_work", "C", 1.0)
_set_role(67, "animation_work", "C", 1.0)
_set_role(75, "3dcg", "C", 1.0)
_set_role(82, "photography", "C", 1.0)
_set_role(84, "setting_production", "C", 1.0)
_set_role(90, "assistant_animation_director", "C", 1.0)
_set_role(91, "assistant_episode_director", "C", 1.0)
_set_role(93, "finishing", "C", 1.0)
_set_role(94, "finishing_check", "C", 1.0)
_set_role(95, "color_check", "C", 1.0)
_set_role(96, "art_board", "C", 1.0)
_set_role(97, "art", "C", 1.0)
_set_role(98, "image_board", "C", 1.0)
_set_role(99, "2d_works", "C", 1.0)
_set_role(100, "3d_works", "C", 1.0)
_set_role(103, "color_script", "C", 1.0)
_set_role(104, "storyboard_cooperation", "C", 1.0)
_set_role(107, "guest_character_design", "C", 1.0)
_set_role(108, "layout_supervision", "C", 1.0)
_set_role(109, "layout_animation_director", "C", 1.0)
_set_role(110, "assistant_chief_animation_director", "C", 1.0)
_set_role(111, "prop_animation_director", "C", 1.0)
_set_role(112, "concept_design", "C", 1.0)
_set_role(113, "costume_design", "C", 1.0)
_set_role(114, "title_design", "C", 1.0)
_set_role(115, "setting_cooperation", "C", 1.0)
_set_role(117, "music_selection", "C", 1.0)
_set_role(118, "inserted_song_lyrics", "C", 1.0)
_set_role(119, "inserted_song_composition", "C", 1.0)
_set_role(120, "inserted_song_arrangement", "C", 1.0)
_set_role(125, "literary_producer", "C", 1.0)
_set_role(129, "bank_storyboard_direction", "C", 1.0)
_set_role(130, "live_storyboard_direction", "C", 1.0)
_set_role(131, "meta_story_storyboard_direction", "C", 1.0)
_set_role(132, "meta_story_character_design", "C", 1.0)
_set_role(135, "tokusatsu_effects", "C", 1.0)
_set_role(136, "visual_effects", "C", 1.0)
_set_role(138, "eyecatch_art", "C", 1.0)
_set_role(139, "illustration", "C", 1.0)
_set_role(142, "mechanical_design_concept", "C", 1.0)
_set_role(143, "concept_art", "C", 1.0)
_set_role(144, "visual_concept", "C", 1.0)
_set_role(145, "scene_design", "C", 1.0)
_set_role(146, "monster_design", "C", 1.0)
_set_role(147, "story_concept", "C", 1.0)
_set_role(148, "scenario_coordinator", "C", 1.0)
_set_role(149, "script_cooperation", "C", 1.0)
_set_role(151, "series_composition_cooperation", "C", 1.0)
_set_role(153, "sound_mixing", "C", 1.0)
_set_role(154, "sound_production_coordinator", "C", 1.0)
_set_role(155, "online_editing", "C", 1.0)
_set_role(156, "offline_editing", "C", 1.0)
_set_role(157, "3d_animator", "C", 1.0)
_set_role(162, "cg_production_coordinator", "C", 1.0)
_set_role(163, "art_production_coordinator", "C", 1.0)
_set_role(165, "assistant_color_designer", "C", 1.0)
_set_role(167, "assistant_production_desk", "C", 1.0)
_set_role(168, "assistant_design_manager", "C", 1.0)

# Tier D: long-tail, collaboration/noise-heavy, or load-more-only roles.
_set_role(23, "assistant_producer_legacy", "D", 0.25)
_set_role(24, "associate_producer_assistant", "D", 0.25)
_set_role(27, "digital_paint", "D", 0.25)
_set_role(38, "publicity", "D", 0.25)
_set_role(40, "recording_assistant", "D", 0.25)
_set_role(51, "in_between_animation", "D", 0.25)
_set_role(55, "music_assistant", "D", 0.25)
_set_role(60, "dialogue_editing", "D", 0.25)
_set_role(61, "post_production_assistant", "D", 0.25)
_set_role(62, "production_assistant_general", "D", 0.25)
_set_role(63, "production", "D", 0.25)
_set_role(64, "production_coordination", "D", 0.25)
_set_role(66, "special_thanks", "D", 0.25)
_set_role(76, "work_assistance", "D", 0.25)
_set_role(81, "assistance", "D", 0.25)
_set_role(83, "production_assistant_assistance", "D", 0.25)
_set_role(105, "storyboard_clean_up", "D", 0.25)
_set_role(127, "planning_cooperation", "D", 0.25)
_set_role(152, "recording_studio", "D", 0.25)


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
        role_tier="D",
        role_weight=0.25,
    )
