"""``video.builder`` 分镜编排测试。"""

from __future__ import annotations

import pytest

from video.builder import (
    BOARD_DURATION,
    INTRO_DURATION,
    MAP_SCORE_DURATION,
    OUTRO_DURATION,
    PLAYER_TABLE_BASE,
    PLAYER_TABLE_PER_ITEM,
    build_spec,
)

PLAYER_FIELDS = {
    "nickname",
    "fullName",
    "team",
    "country",
    "rating",
    "kills",
    "deaths",
    "kpr",
    "adr",
    "survivalPr",
    "roundSwing",
    "openingKpr",
    "assistsPr",
}


def test_scene_sequence_and_title(sample_result):
    spec = build_spec(sample_result)

    assert spec.title == "Alpha vs Bravo"
    assert [s.type for s in spec.scenes] == [
        "intro",
        "map_score",
        "player_table",
        "map_score",
        "player_table",
        "player_board",
        "outro",
    ]
    assert [s.id for s in spec.scenes[:3]] == ["intro", "map-0", "map-0-players"]


def test_durations(sample_result):
    spec = build_spec(sample_result)
    player_count = len(sample_result.maps[0].players)

    assert spec.scenes[0].duration == INTRO_DURATION
    assert spec.scenes[1].duration == MAP_SCORE_DURATION
    assert spec.scenes[2].duration == round(
        PLAYER_TABLE_BASE + PLAYER_TABLE_PER_ITEM * player_count, 2
    )
    assert spec.scenes[-2].duration == BOARD_DURATION
    assert spec.scenes[-1].duration == OUTRO_DURATION


def test_intro_data(sample_result):
    data = build_spec(sample_result).scenes[0].data

    assert data["event"] == "Test Cup 2026"
    assert data["time"] == "2026-01-02 20:30"
    assert data["mapCount"] == 2
    assert [t["name"] for t in data["teams"]] == ["Alpha", "Bravo"]
    assert data["teams"][0]["won"] is True
    assert data["teams"][1]["won"] is False


def test_map_score_data(sample_result):
    data = build_spec(sample_result).scenes[1].data

    assert data["index"] == 1
    assert data["total"] == 2
    assert data["mapName"] == "Mirage"
    assert data["rounds"] == 22
    assert data["teams"][0]["won"] is True
    assert data["teams"][1]["won"] is False


def test_map_players_have_all_fields(sample_result):
    table = build_spec(sample_result).scenes[2].data

    assert table["mapName"] == "Mirage"
    assert table["rounds"] == 22
    assert table["teams"] == ["Alpha", "Bravo"]
    assert len(table["players"]) == len(sample_result.maps[0].players)

    for player in table["players"]:
        assert PLAYER_FIELDS <= set(player)
        # 本期首杀/助攻固定缺失
        assert player["openingKpr"] is None
        assert player["assistsPr"] is None


def test_map_players_sorted_by_rating_within_team(sample_result):
    players = build_spec(sample_result).scenes[2].data["players"]

    for team in ("Alpha", "Bravo"):
        ratings = [p["rating"] for p in players if p["team"] == team]
        assert ratings == sorted(ratings, reverse=True)


def test_survival_pr_matches_source(sample_result):
    players = build_spec(sample_result).scenes[2].data["players"]
    view = players[0]
    source = next(
        p for p in sample_result.maps[0].players if p.nickname == view["nickname"]
    )

    assert view["survivalPr"] == pytest.approx(source.survival / 100, abs=1e-3)


def test_board_scene(sample_result):
    data = build_spec(sample_result).scenes[-2].data

    assert data["topOpening"] == []  # 本期无首杀数据
    for key in ("topRating", "topAdr", "topKpr", "topRoundSwing"):
        values = [item["value"] for item in data[key]]
        assert values == sorted(values, reverse=True)
        assert all(v is not None for v in values)
    names = [item["nickname"] for item in data["topRating"]]
    assert len(names) == len(set(names))


def test_outro_mvp_is_highest_rated(sample_result):
    data = build_spec(sample_result).scenes[-1].data

    assert data["mvp"]["nickname"] == "al0"
    assert data["mapCount"] == 2
    assert data["teams"][0]["won"] is True


def test_custom_meta(sample_result):
    spec = build_spec(sample_result, width=1280, height=720, fps=30, theme="dark")

    assert (spec.width, spec.height, spec.fps, spec.theme) == (1280, 720, 30, "dark")
