# TODO

## 爬虫与数据

### 已完成

- [x] 抓取 HLTV 赛果列表页并解析比赛详情链接（`parse_results`）。
- [x] 请求层加固：超时、失败重试（指数退避）、请求随机间隔限速（`fetch`）。
- [x] 解析单场比赛基础信息：赛事名称、比赛时间、双方总比分（`_parse_event_name` / `_parse_match_time`）。
- [x] 解析每张地图的名称、比分、回合数与选手统计页地址（`MapResultData`）。
- [x] 解析全场与单图选手数据：K-D、eK-D、Round Swing、ADR、eADR、KAST、eKAST、KPR、生存率、Rating（`parse_player_stats_tables`）。
- [x] 校验地图与统计块一一对应，字段缺失时抛出明确异常。
- [x] 终端格式化输出比赛结果与重点选手数据表（`print_match_result`）。

### 待办

- [ ] 支持批量抓取多场比赛（当前 `main` 仅处理 `match_urls[:1]`）。
- [ ] 支持通过比赛 ID、URL、日期或参赛队伍选取特定比赛。
- [ ] 结果导出为结构化文件（JSON / CSV），供后续视频或文章使用。
- [ ] （**延后**）在 HLTV 上定位并补充抓取每图每选手的**首杀**与**助攻**：比赛页 “Detailed stats” → `/stats/matches/<id>/<teamA>-vs-<teamB>`（线索与方案见 [docs/video-pipeline-design.md](./docs/video-pipeline-design.md) §10.1）。
- [ ] 为无法获取的统计字段增加统一的错误报告和记录机制。

> 当前视频阶段**先只用 HLTV 现有的 5 项**：Rating / 场均击杀 / 场均伤害 / 场均存活 / Round Swing；
> 首杀与助攻留到后续版本，数据模型保留字段、缺失时置 `null` 显示 `—`。

## 视频制作

> 生成方式选型见 [docs/video-generation-research.md](./docs/video-generation-research.md)，
> 完整方案设计（架构、分镜、模块、里程碑）见 [docs/video-pipeline-design.md](./docs/video-pipeline-design.md)。
>
> **本期范围（已定）**：选手数据先做 HLTV 现有的 5 项——Rating / 场均击杀 / 场均伤害 / 场均存活 / Round Swing；
> 场均首杀与场均助攻延后，后续在 HLTV 详细统计页定位后补充抓取（不引入 GOTV）。

- [x] **M1 骨架**：`video/model.py` / `scenes.py` / `builder.py` / `cli.py`，`python -m video.cli spec --html match.html` 可导出 VideoSpec（含每图选手数据幕）。
- [ ] M2 链路：`renderer.py` + `encoder.py`，产出无声 MP4。
- [ ] M3 数据幕：`map_score` / `player_table` / `outro` 模板。
- [ ] M4 动效：`renderFrame(t)` 驱动的数字滚动与入场动画。
- [ ] M5 打磨：主题化、榜单幕、预览模式。
- [ ] M6 批量：多 URL 批处理与背景音乐。

- [ ] 设计比赛结果视频模板和视觉风格。
- [ ] 根据比赛、地图和选手数据生成视频分镜与时间轴。
- [ ] 渲染赛事信息、地图比分、选手数据和重点统计。
- [ ] 统一配色/字体/转场，保证数据可读性（视频不含解说与字幕）。
- [ ] 输出 MP4 视频并进行播放与画质检查。

## 工程化

- [x] 补充 `requirements.txt`（requests / beautifulsoup4 / lxml / playwright；另需系统级 ffmpeg）。
- [x] 分镜与 CLI 单元测试（pytest，22 项）＋ `requirements-dev.txt` / `pytest.ini`。
- [ ] 增加命令行参数入口（选择比赛、输出格式、是否生成视频）。
- [ ] 增加日志与调试开关，支持保存原始 HTML 便于排查。
- [ ] 模板契约测试（每个模板都导出 `initScene` / `renderFrame`）。
- [ ] 渲染冒烟测试（渲染 2s 短片并用 ffprobe 验证）。
