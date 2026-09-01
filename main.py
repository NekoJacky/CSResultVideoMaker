import time
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import header
from urllib.parse import urljoin


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ===== 配置 =====
BASE_URL = "https://www.hltv.org/results"
HLTV_URL = "https://www.hltv.org"
HEADERS = header.HEADERS
TIMEOUT = 15
RETRIES = 3
RETRY_BACKOFF = 2  # 秒，指数退避基数


# ===== 数据结构 =====
@dataclass
class TeamResult:
    team_name: str = ""
    score: int = 0


@dataclass
class PlayerResultData:
    team_name: str = str()
    full_name: str = str()
    nickname: str = str()
    country: str = str()
    kills: int = 0
    deaths: int = 0
    economy_adjusted_kills: int = 0
    economy_adjusted_deaths: int = 0
    round_swing: float = 0.0
    adr: float = 0.0
    economy_adjusted_adr: float = 0.0
    kast: float = 0.0
    economy_adjusted_kast: float = 0.0
    rating: float = 0.0


@dataclass
class MapResultData:
    map_name: str = ""
    team_results_on_map: list[TeamResult] = field(default_factory=list)


@dataclass
class ResultData:
    teams: list[str] = field(default_factory=list)
    match_time: datetime | None = None
    team_results: list[TeamResult] = field(default_factory=list)
    maps: list[MapResultData] = field(default_factory=list)
    players: list[PlayerResultData] = field(default_factory=list)


# ===== 请求层 =====
def fetch(url: str) -> str:
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return resp.text
        except requests.RequestException as exc:
            wait = RETRY_BACKOFF ** attempt
            log.warning("请求失败 %s 第%d次: %s，%ds 后重试", url, attempt, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"抓取失败，重试耗尽: {url}")


# ===== 解析层 =====
def parse_results(html: str) -> list[str]:
    urls: list[str] = []
    soup = BeautifulSoup(html, "lxml")
    big_results = soup.select("div.big-results")[0]
    result_con = big_results.select("div.result-con")
    for result in result_con:
        link_tag = result.find('a', class_='a-reset')
        if link_tag:
            param: str
            herf = link_tag.get("href")
            if herf is None:
                continue
            if isinstance(herf, list):
                if not herf:
                    continue
                param = herf[0]
            else:
                param = herf
            if not param:
                continue
            url = urljoin(HLTV_URL, param)
            urls.append(url)
            # parse_results(url)
    return urls


def parse_player_stats_tables(stats_content) -> list[PlayerResultData]:
    players: list[PlayerResultData] = []
    for table in stats_content.select("table.totalstats"):
        team_name_tag = table.select_one("tr.header-row a.teamName")
        team_name = team_name_tag.get_text(strip=True) if team_name_tag else ""
        for row in table.select("tr:not(.header-row)"):
            nickname_tag = row.select_one(".smartphone-only.statsPlayerName")
            full_name_tag = row.select_one(".gtSmartphone-only.statsPlayerName")
            country_tag = row.select_one("img.flag")
            kills, deaths = _parse_score_pair(row.select_one("td.kd.traditional-data"))
            adjusted_kills, adjusted_deaths = _parse_score_pair(
                row.select_one("td.kd.eco-adjusted-data")
            )
            players.append(
                PlayerResultData(
                    team_name=team_name,
                    full_name=_normalize_name(full_name_tag),
                    nickname=nickname_tag.get_text(strip=True) if nickname_tag else "",
                    country=country_tag.get("alt", "") if country_tag else "",
                    kills=kills,
                    deaths=deaths,
                    economy_adjusted_kills=adjusted_kills,
                    economy_adjusted_deaths=adjusted_deaths,
                    round_swing=_parse_stat_float(row.select_one("td.roundSwing")),
                    adr=_parse_stat_float(row.select_one("td.adr.traditional-data")),
                    economy_adjusted_adr=_parse_stat_float(
                        row.select_one("td.adr.eco-adjusted-data")
                    ),
                    kast=_parse_stat_float(row.select_one("td.kast.traditional-data")),
                    economy_adjusted_kast=_parse_stat_float(
                        row.select_one("td.kast.eco-adjusted-data")
                    ),
                    rating=_parse_stat_float(row.select_one("td.rating")),
                )
            )
    return players


def _parse_score_pair(tag) -> tuple[int, int]:
    if tag is None:
        return 0, 0
    values = tag.get_text(strip=True).split("-")
    if len(values) != 2:
        return 0, 0
    try:
        return int(values[0]), int(values[1])
    except ValueError:
        return 0, 0


def _parse_stat_float(tag) -> float:
    if tag is None:
        return 0.0
    try:
        return float(tag.get_text(strip=True).rstrip("%"))
    except ValueError:
        return 0.0


def _normalize_name(tag) -> str:
    if tag is None:
        return ""
    return " ".join(tag.get_text(" ", strip=True).split())


def _parse_match_time(soup: BeautifulSoup) -> datetime | None:
    time_tag = soup.select_one("div.timeAndEvent div.time")
    if time_tag is None:
        return None

    date_tag = soup.select_one("div.timeAndEvent div.date")
    if date_tag:
        try:
            time_text = time_tag.get_text(strip=True)
            date_text = date_tag.get_text(strip=True)
            date_text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_text)
            return datetime.strptime(time_text + " " + date_text, "%H:%M %d of %B %Y")
        except ValueError:
            pass

    data_unix = time_tag.get("data-unix")
    if data_unix:
        try:
            return datetime.fromtimestamp(int(data_unix) / 1000)
        except (TypeError, ValueError):
            pass


def print_player_table(players: list[PlayerResultData]) -> None:
    print(
        f"{'Team':<10} {'Player':<10} {'Country':<22} "
        f"{'K-D':>5} {'eK-D':>5} {'Swing':>7} "
        f"{'ADR':>6} {'eADR':>6} {'KAST':>6} {'eKAST':>6} {'Rating':>7}"
    )
    print("-" * 105)
    for player in players:
        print(
            f"{player.team_name[:10]:<10} "
            f"{player.nickname[:10]:<10} "
            f"{player.country[:22]:<22} "
            f"{player.kills:>2}-{player.deaths:<2} "
            f"{player.economy_adjusted_kills:>2}-{player.economy_adjusted_deaths:<2} "
            f"{player.round_swing:>6.2f}% "
            f"{player.adr:>6.1f} "
            f"{player.economy_adjusted_adr:>6.1f} "
            f"{player.kast:>5.1f}% "
            f"{player.economy_adjusted_kast:>5.1f}% "
            f"{player.rating:>7.2f}"
        )


def format_team_scores(team_results: list[TeamResult]) -> str:
    if len(team_results) < 2:
        return "  ".join(
            f"{team_result.team_name} {team_result.score}"
            for team_result in team_results
        )
    first_team, second_team = team_results[:2]
    return (
        f"{first_team.team_name} {first_team.score} - "
        f"{second_team.score} {second_team.team_name}"
    )


def print_match_result(result: ResultData) -> None:
    scores = format_team_scores(result.team_results)
    print("=" * 105)
    print(f"比赛结果: {scores}")
    if result.match_time:
        print(f"比赛时间: {result.match_time.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 105)

    print("全场选手数据")
    print_player_table(result.players)

    for map_result in result.maps:
        map_scores = format_team_scores(map_result.team_results_on_map)
        print()
        print(f"{map_result.map_name}: {map_scores}")
        print_player_table(map_result.players)


def parse_matches_result(urls: list[str]) -> list[ResultData]:
    results: list[ResultData] = []
    for url in urls:
        html = fetch(url)
        # with open("match.html", "w", encoding="utf-8") as f:
            # f.write(html)
        results.append(parse_match_result(html))
    return results


def parse_match_result(html: str) -> ResultData:
    soup = BeautifulSoup(html, "lxml")
    match_time = _parse_match_time(soup)
    team_results: list[TeamResult] = []
    teams = soup.select("div.team")
    for team in teams:
        team_name = ""
        score = 0
        tmp_team_name = team.select_one("div.teamName")
        if tmp_team_name:
            team_name = tmp_team_name.get_text(strip=True)
        tmp = team.select_one("div.won")
        if tmp is None:
            tmp = team.select_one("div.lost")
        if tmp:
            try:
                score = int(tmp.get_text(strip=True))
            except ValueError:
                score = 0
        team_results.append(TeamResult(team_name=team_name, score=score))
        # log.info("Team: %-20s Score: %d", team_name, score)

    map_holders = soup.select("div.mapholder")
    maps: list[MapResultData] = []
    for map_holder in map_holders:
        map_name_tag = map_holder.select_one("div.mapname")
        if map_name_tag is None:
            continue
        map_name = map_name_tag.get_text(strip=True)

        team_name_tags = map_holder.select("div.results-teamname")
        score_tags = map_holder.select("div.results-team-score")
        map_results = [
            TeamResult(
                team_name=team_name_tag.get_text(strip=True),
                score=int(score_tag.get_text(strip=True)),
            )
            for team_name_tag, score_tag in zip(team_name_tags, score_tags)
        ]
        maps.append(MapResultData(map_name=map_name, team_results_on_map=map_results))
        # log.info("    Map: %s", map_name)

    stats_contents = soup.select("div.matchstats > div.stats-content")
    players = parse_player_stats_tables(stats_contents[0]) if stats_contents else []
    for map_result, stats_content in zip(maps, stats_contents[1:]):
        map_result.players = parse_player_stats_tables(stats_content)

    return ResultData(
        teams=[team_result.team_name for team_result in team_results],
        match_time=match_time,
        team_results=team_results,
        maps=maps,
        players=players,
    )


# ===== 主流程 =====
def main() -> None:
    # html = fetch(BASE_URL)
    # with open("main.html", "w", encoding="utf-8") as f:
        # f.write(html)
    # with open("main.html", "r", encoding="utf-8") as f:
        # html = f.read()
    # match_urls = parse_results(html)
    # parse_matches_result(match_urls)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with open("match.html", "r", encoding="utf-8") as f:
        html = f.read()
    result = parse_match_result(html)
    print_match_result(result)


if __name__ == "__main__":
    main()
