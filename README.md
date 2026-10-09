# CS Result Video Maker

尝试写个自动化脚本生成数据视频，不行的话生成数据文章也可以。

当前进度：**数据采集与解析已完成**，可抓取 HLTV 赛果并输出比赛与选手数据；视频生成部分尚未开始。

## 功能

- 抓取 [HLTV 赛果页](https://www.hltv.org/results)，解析比赛详情链接。
- 解析单场比赛信息：
  - 赛事名称、比赛时间、双方总比分。
  - 每张地图的名称、比分与回合数。
- 解析选手数据（全场 + 每张地图）：
  - K-D、经济调整 K-D（eK-D）
  - Round Swing、ADR、eADR
  - KAST、eKAST
  - KPR、生存率、Rating
- 终端格式化输出比赛结果表与重点选手数据表。
- 请求层加固：超时、失败重试（指数退避）、随机请求间隔限速。
- 解析结果做一致性校验：地图数与统计块一一对应、字段缺失时抛出明确异常。

## 环境要求

- Python 3.10+（使用 `X | None`、`list[...]` 等类型语法；开发环境为 3.13）
- 依赖：`requests`、`beautifulsoup4`、`lxml`（见 [requirements.txt](./requirements.txt)）

安装：

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
pip install -r requirements.txt
```

## 使用

```bash
python main.py
```

脚本会抓取 HLTV 赛果页，解析**第一场**比赛并在终端打印结果。

> 注意：脚本会实时请求 HLTV，请遵守目标站点的使用条款并控制抓取频率。

## 输出示例

```
=========================================================================================================
比赛结果: Team A 2 - 1 Team B
赛事名称: Some Event 2025
比赛时间: 2025-01-01 20:00
=========================================================================================================
全场选手数据（80 回合）
Team       Player     Country                K-D   eK-D   Swing    ADR   eADR   KAST  eKAST   KPR   Surv  Rating
------------------------------------------------------------------------------------------------------------
Team A     player1    Denmark              55-40  52-41   2.10%   85.3   83.1  72.5%  71.0%  0.69   50.0%    1.25
...
```

重点选手数据部分会分别打印「全场」与每张地图的 KPR / 生存率 / Round Swing / ADR / KAST / Rating 摘要。

## 配置

主要参数集中在 `main.py` 顶部：

| 常量 | 说明 | 默认值 |
| --- | --- | --- |
| `BASE_URL` | 赛果列表页地址 | `https://www.hltv.org/results` |
| `TIMEOUT` | 单次请求超时（秒） | `15` |
| `RETRIES` | 请求最大尝试次数 | `3` |
| `RETRY_BACKOFF` | 重试指数退避基数（秒） | `2` |
| `MIN_REQUEST_DELAY` / `MAX_REQUEST_DELAY` | 请求间随机间隔区间（秒） | `0.5` / `2.0` |

## 项目结构

```
├── main.py           # 入口：抓取、解析、数据结构与终端输出
├── header.py         # 请求头（User-Agent 等）
├── requirements.txt  # Python 依赖
├── todo.md           # 任务清单与进度
└── README.md         # 项目说明
```

## 数据结构

`main.py` 中使用 dataclass 描述解析结果：

- `TeamResult`：队伍名与比分。
- `PlayerResultData`：单名选手的完整统计数据。
- `MapResultData`：单图比分、回合数与选手数据。
- `ResultData`：整场比赛（赛事、时间、总比分、地图、全场选手数据）。

解析流程：

1. `fetch` 抓取页面（含限速与重试）。
2. `parse_results` 从赛果页提取比赛详情链接。
3. `parse_match_result` 解析比赛信息、地图比分与统计块。
4. `parse_player_stats_tables` 解析全场与单图选手数据。
5. `print_match_result` 格式化输出。

## 已知限制

- 每次运行仅处理赛果页第一场比赛（`main` 中 `match_urls[:1]`）。
- 仅支持已结束且带统计数据的比赛，页面结构变化可能导致解析异常。
- 结果目前只打印到终端，尚未落盘为 JSON / CSV。

## 路线图

- [ ] 批量抓取与按条件（ID / URL / 日期 / 队伍）选取比赛。
- [ ] 数据导出（JSON / CSV）。
- [ ] 设计视频模板并生成分镜与时间轴。
- [ ] 渲染地图比分、选手数据与重点统计。
- [ ] 接入 TTS 解说与字幕，输出 MP4。

详细任务见 [todo.md](./todo.md)。
