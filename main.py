import time
import logging
from dataclasses import dataclass, field
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
class MapResultData:
    map_name: str = ""
    team_results_on_map: list[TeamResult] = field(default_factory=list)


@dataclass
class ResultData:
    teams: list[str] = field(default_factory=list)
    team_result: TeamResult = TeamResult()
    maps: list[MapResultData] = field(default_factory=list)


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


def parse_matches_result(urls:list[str]) -> None:
    result = ResultData()
    for url in urls:
        html = fetch(url)
        # with open("match.html", "w", encoding="utf-8") as f:
            # f.write(html)
        parse_match_result(html)


def parse_match_result(html:str) -> None:
    soup = BeautifulSoup(html, "lxml")
    teams = soup.select("div.team")
    for team in teams:
        team_name:str = ""
        score: str = ""
        tmp_team_name = team.select_one("div.teamName")
        if tmp_team_name:
            team_name = tmp_team_name.get_text(strip=True)
        tmp = team.select_one("div.won")
        if tmp is None:
            tmp = team.select_one("div.lost")
        if tmp:
            score = tmp.get_text(strip=True)
        log.info("Team: %-8s Score: %s", team_name, score)
    map_holders = soup.select("div.mapholder")
    for map_holder in map_holders:
        map_name: str = ""
        map_names = map_holder.select("div.mapname")
        if map_names:
            map_name = map_names[0].get_text()
            log.info("    Map: %s", map_name)


# ===== 主流程 =====
def main() -> None:
    # html = fetch(BASE_URL)
    # with open("main.html", "w", encoding="utf-8") as f:
        # f.write(html)
    # with open("main.html", "r", encoding="utf-8") as f:
        # html = f.read()
    # match_urls = parse_results(html)
    # parse_matches_result(match_urls)
    with open("match.html", 'r', encoding="utf-8") as f:
        html = f.read()
    parse_match_result(html)


if __name__ == "__main__":
    main()
