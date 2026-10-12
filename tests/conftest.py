"""pytest 公共夹具：构造不依赖网络的 ``ResultData``。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import MapResultData, PlayerResultData, ResultData, TeamResult  # noqa: E402

ALPHA = "Alpha"
BRAVO = "Bravo"


def make_player(
    nickname: str,
    team: str,
    *,
    kills: int,
    deaths: int,
    rounds: int,
    adr: float,
    rating: float,
    round_swing: float,
    country: str = "Testland",
) -> PlayerResultData:
    return PlayerResultData(
        team_name=team,
        full_name=f"{nickname} Real",
        nickname=nickname,
        country=country,
        kills=kills,
        deaths=deaths,
        rounds=rounds,
        kpr=kills / rounds if rounds else 0.0,
        survival=(rounds - deaths) / rounds * 100 if rounds else 0.0,
        round_swing=round_swing,
        adr=adr,
        rating=rating,
    )


def _map_players(rounds: int, offset: float) -> list[PlayerResultData]:
    """每队 3 人，rating 依次递减，便于断言排序。"""
    players: list[PlayerResultData] = []
    for team, base in ((ALPHA, 1.30), (BRAVO, 1.10)):
        for i in range(3):
            players.append(
                make_player(
                    f"{team[:2].lower()}{i}",
                    team,
                    kills=rounds // 2 - i,
                    deaths=rounds // 3 + i,
                    rounds=rounds,
                    adr=90.0 - i * 5 + offset,
                    rating=base - i * 0.1,
                    round_swing=3.0 - i,
                )
            )
    return players


@pytest.fixture
def sample_maps() -> list[MapResultData]:
    return [
        MapResultData(
            map_name="Mirage",
            team_results_on_map=[
                TeamResult(ALPHA, 13),
                TeamResult(BRAVO, 9),
            ],
            rounds=22,
            players=_map_players(22, 0.0),
            stats_url="https://www.hltv.org/stats/matches/mapstatsid/1/alpha-vs-bravo",
        ),
        MapResultData(
            map_name="Inferno",
            team_results_on_map=[
                TeamResult(ALPHA, 11),
                TeamResult(BRAVO, 13),
            ],
            rounds=24,
            players=_map_players(24, 1.0),
            stats_url="https://www.hltv.org/stats/matches/mapstatsid/2/alpha-vs-bravo",
        ),
    ]


@pytest.fixture
def sample_result(sample_maps: list[MapResultData]) -> ResultData:
    overall_rounds = sum(m.rounds for m in sample_maps)
    overall_players = _map_players(overall_rounds, 0.5)
    # 让全场 MVP 唯一：把 Alpha 的第一人拉高
    overall_players[0].rating = 1.75
    return ResultData(
        teams=[ALPHA, BRAVO],
        event_name="Test Cup 2026",
        match_time=datetime(2026, 1, 2, 20, 30),
        team_results=[TeamResult(ALPHA, 2), TeamResult(BRAVO, 1)],
        maps=sample_maps,
        rounds=overall_rounds,
        players=overall_players,
    )
