"""把 ``ResultData`` 编排成 ``VideoSpec``。

这里是「时间轴与分镜」的唯一来源：时长、顺序、每幕展示的数据都在此决定。
衍生统计（MVP、榜单）也在这里算好，模板保持纯展示。

本期选手字段（见 docs/video-pipeline-design.md §3.3）：
    rating / kpr(场均击杀) / adr(场均伤害) / survivalPr(场均存活) / roundSwing
``openingKpr`` 与 ``assistsPr`` 暂缺，固定为 None，待 HLTV 补充抓取后填充。
"""

from __future__ import annotations

from typing import Any

from main import MapResultData, PlayerResultData, ResultData

from .model import Scene, VideoSpec

# ===== 时长配置（秒）=====
INTRO_DURATION = 3.5
MAP_SCORE_DURATION = 4.0
BOARD_DURATION = 6.0
OUTRO_DURATION = 3.0
PLAYER_TABLE_BASE = 2.0
PLAYER_TABLE_PER_ITEM = 0.5

# 榜单条数
TOP_N = 5


def build_spec(
    result: ResultData,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    theme: str = "default",
) -> VideoSpec:
    """根据一场比赛结果编排完整分镜。"""
    spec = VideoSpec(
        width=width,
        height=height,
        fps=fps,
        theme=theme,
        title=_title(result),
    )
    spec.add(Scene("intro", "intro", INTRO_DURATION, _intro_data(result)))
    for index, map_result in enumerate(result.maps):
        spec.add(
            Scene(
                f"map-{index}",
                "map_score",
                MAP_SCORE_DURATION,
                _map_score_data(map_result, index, len(result.maps)),
            )
        )
        spec.add(
            Scene(
                f"map-{index}-players",
                "player_table",
                _player_table_duration(len(map_result.players)),
                _map_players_data(map_result),
            )
        )
    spec.add(Scene("board", "player_board", BOARD_DURATION, _board_data(result)))
    spec.add(Scene("outro", "outro", OUTRO_DURATION, _outro_data(result)))
    return spec


# ===== 各幕数据 =====
def _intro_data(result: ResultData) -> dict[str, Any]:
    return {
        "event": result.event_name,
        "time": (
            result.match_time.strftime("%Y-%m-%d %H:%M")
            if result.match_time
            else None
        ),
        "totalRounds": result.rounds,
        "mapCount": len(result.maps),
        "teams": _team_scores(result.team_results),
    }


def _map_score_data(
    map_result: MapResultData, index: int, total: int
) -> dict[str, Any]:
    return {
        "index": index + 1,
        "total": total,
        "mapName": map_result.map_name,
        "rounds": map_result.rounds,
        "teams": _team_scores(map_result.team_results_on_map),
    }


def _map_players_data(map_result: MapResultData) -> dict[str, Any]:
    players = [_player_view(player) for player in map_result.players]
    players.sort(key=lambda p: (p["team"], -p["rating"]))
    return {
        "mapName": map_result.map_name,
        "rounds": map_result.rounds,
        "teams": _team_order(map_result.players),
        "players": players,
    }


def _board_data(result: ResultData) -> dict[str, Any]:
    players = [_player_view(player) for player in result.players]
    return {
        "teams": _team_order(result.players),
        "topRating": _top(players, "rating"),
        "topAdr": _top(players, "adr"),
        "topKpr": _top(players, "kpr"),
        "topRoundSwing": _top(players, "roundSwing"),
        "topOpening": _top(players, "openingKpr"),  # 本期恒为空
    }


def _outro_data(result: ResultData) -> dict[str, Any]:
    mvp = max(result.players, key=lambda p: p.rating, default=None)
    return {
        "event": result.event_name,
        "totalRounds": result.rounds,
        "mapCount": len(result.maps),
        "teams": _team_scores(result.team_results),
        "mvp": _player_view(mvp) if mvp else None,
    }


# ===== 视图辅助 =====
def _title(result: ResultData) -> str:
    if len(result.teams) >= 2:
        return f"{result.teams[0]} vs {result.teams[1]}"
    return result.teams[0] if result.teams else "CS Result"


def _team_scores(team_results) -> list[dict[str, Any]]:
    if not team_results:
        return []
    best = max(tr.score for tr in team_results)
    return [
        {"name": tr.team_name, "score": tr.score, "won": tr.score == best}
        for tr in team_results
    ]


def _team_order(players: list[PlayerResultData]) -> list[str]:
    seen: list[str] = []
    for player in players:
        if player.team_name and player.team_name not in seen:
            seen.append(player.team_name)
    return seen


def _player_view(player: PlayerResultData) -> dict[str, Any]:
    return {
        "nickname": player.nickname,
        "fullName": player.full_name,
        "team": player.team_name,
        "country": player.country,
        "rating": round(player.rating, 2),
        "kills": player.kills,
        "deaths": player.deaths,
        "kpr": round(player.kpr, 3),
        "adr": round(player.adr, 1),
        "survivalPr": round(player.survival / 100.0, 3) if player.rounds else None,
        "roundSwing": round(player.round_swing, 2),
        # 待 HLTV 补充抓取（见 docs/video-pipeline-design.md §10.1）
        "openingKpr": None,
        "assistsPr": None,
    }


def _top(players: list[dict[str, Any]], key: str, n: int = TOP_N) -> list[dict[str, Any]]:
    available = [p for p in players if p.get(key) is not None]
    available.sort(key=lambda p: p[key], reverse=True)
    return [
        {"nickname": p["nickname"], "team": p["team"], "value": p[key]}
        for p in available[:n]
    ]


def _player_table_duration(player_count: int) -> float:
    return round(PLAYER_TABLE_BASE + PLAYER_TABLE_PER_ITEM * player_count, 2)
