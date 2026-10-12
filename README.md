# CS Result Video Maker

尝试写个自动化脚本生成数据视频，不行的话生成数据文章也可以。

当前进度：**数据采集与解析已完成**；视频生成已完成 M1（分镜 VideoSpec）与 M2（Playwright 渲染 + ffmpeg 编码，可产出无声 MP4），下一步是 M3 数据幕与 M4 动效。

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
- 依赖：`requests`、`beautifulsoup4`、`lxml`、`playwright`（见 [requirements.txt](./requirements.txt)）
- 视频编码另需系统级 `ffmpeg`（Windows: `winget install Gyan.FFmpeg`）

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

生成视频请用 `python -m video.cli`，见下方[视频生成](#视频生成)。

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

## 视频生成

`video/` 是视频生成流水线，设计见 [docs/video-pipeline-design.md](./docs/video-pipeline-design.md)。
入口为 `python -m video.cli <命令>`，支持三个子命令：

| 命令 | 说明 | 状态 |
| --- | --- | --- |
| `spec` | 导出 VideoSpec JSON（分镜调试） | ✅ 可用 |
| `build` | Playwright 逐帧渲染 + ffmpeg 编码为无声 MP4 | ✅ 可用（M2） |
| `preview` | 渲染每幕关键帧 PNG | ⏳ M5 |

### 指定比赛（数据来源）

三个命令都通过 `--html` / `--url` 二选一指定比赛：

- `--html match.html`：使用本地比赛页，不联网，适合调试。
- `--url "https://www.hltv.org/matches/xxx/..."`：实时抓取该比赛页。

想直接对 HLTV **最新一场**比赛出片时，可先取赛果页第一个链接：

```bash
# 打印最新比赛 URL
.venv/Scripts/python.exe -c "import main; print(main.parse_results(main.fetch(main.BASE_URL))[0])"
```

### 导出分镜（spec）

```bash
# 从本地比赛页
python -m video.cli spec --html match.html --out output/spec.json

# 或实时抓取比赛页（缺省 --out 时打印 JSON 到终端）
python -m video.cli spec \
    --url "https://www.hltv.org/matches/2398757/vitality-vs-mouz-esl-pro-league-season-24" \
    --out output/spec.json
```

### 生成视频（build）

```bash
# 从本地比赛页（1080p@60fps）
python -m video.cli build --html match.html --out output/result.mp4

# 实时抓取最新比赛（1080p@60fps）
python -m video.cli build \
    --url "https://www.hltv.org/matches/2398757/vitality-vs-mouz-esl-pro-league-season-24" \
    --out output/result.mp4 \
    --resolution 1920x1080 --fps 60 --theme default

# 快速测试（720p@30fps，渲染更快）
python -m video.cli build \
    --url "https://www.hltv.org/matches/2398757/vitality-vs-mouz-esl-pro-league-season-24" \
    --out output/result_720p.mp4 \
    --resolution 1280x720 --fps 30

# 加背景音乐（可选）
python -m video.cli build --html match.html --out output/result.mp4 --music bgm.mp3
```

### 命令参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--html` / `--url` | 必选其一 | 本地比赛页 / HLTV 比赛页 |
| `--out` | `output/result.mp4`（build）/ `output/preview`（preview） | 输出路径；spec 缺省打印到终端 |
| `--fps` | `60` | 帧率（测试可降到 30） |
| `--resolution` | `1920x1080` | 输出分辨率，格式 `宽x高` |
| `--theme` | `default` | 主题名，见 `templates/themes/`（`default` / `dark`） |
| `--music` | 无 | 背景音乐路径（可选，自动压到 -18dB） |

### 渲染与编码说明

- 浏览器按 **系统 Edge → Chrome → 内置 Chromium** 逐级回退，无需手动下载 Chromium。
- 编码优先 `h264_nvenc`，探测不到时自动回退 `libx264`。
- 输出统一为 `yuv420p` + tv-range，保证 B 站 / 微信 / QuickTime 等播放器兼容。
- 渲染为「逐帧截图 + 管道直喂 ffmpeg」，不落盘中间帧，磁盘占用仅输出 MP4。

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
├── main.py                # 入口：抓取、解析、数据结构与终端输出
├── header.py              # 请求头（User-Agent 等）
├── video/                 # 视频生成流水线（M1 分镜 + M2 渲染编码）
│   ├── model.py           # VideoSpec / Scene
│   ├── scenes.py          # 场景类型注册表
│   ├── builder.py         # ResultData -> VideoSpec
│   ├── renderer.py        # Playwright 逐帧渲染（JPEG 帧流）
│   ├── encoder.py         # ffmpeg 编码 MP4（NVENC / libx264）
│   └── cli.py             # python -m video.cli
├── templates/             # 表现层（HTML/CSS/JS + 主题）
│   ├── base.css / base.js
│   ├── scenes/            # intro / map_score / player_table / player_board / outro
│   └── themes/            # default.json / dark.json
├── tests/                 # 单元测试（pytest）
├── docs/                  # 调研与设计文档
├── requirements.txt       # 运行依赖
├── requirements-dev.txt   # 开发/测试依赖
├── todo.md                # 任务清单与进度
└── README.md              # 项目说明
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

## 开发与测试

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## 已知限制

- 每次运行仅处理赛果页第一场比赛（`main` 中 `match_urls[:1]`）。
- 仅支持已结束且带统计数据的比赛，页面结构变化可能导致解析异常。
- `main.py` 的解析结果目前只打印到终端，尚未直接导出 JSON / CSV（视频分镜可通过 `spec` 命令导出 JSON）。

## 路线图

- [ ] 批量抓取与按条件（ID / URL / 日期 / 队伍）选取比赛。
- [ ] 数据导出（JSON / CSV）。
- [x] 设计视频模板并生成分镜与时间轴（M1）。
- [x] 渲染 + 编码链路，输出无声 MP4（M2）。
- [ ] 数据幕细化：`map_score` / `player_table` / `outro` 全量呈现与视觉打磨（M3）。
- [ ] 动效：`renderFrame(t)` 数字滚动与入场动画（M4）。

详细任务见 [todo.md](./todo.md)；视频生成选型见 [docs/video-generation-research.md](./docs/video-generation-research.md)，完整方案设计见 [docs/video-pipeline-design.md](./docs/video-pipeline-design.md)。
