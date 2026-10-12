# 视频生成方案设计（Video Pipeline Design）

> 目标：把现有 `ResultData`（HLTV 赛果 + 选手统计）稳定、可复现地渲染成**纯数据呈现**的 MP4。
> 不使用解说、不使用字幕，音频最多只加背景音乐。
> 相关调研见 [video-generation-research.md](./video-generation-research.md)。

---

## 1. 目标与范围

### 1.1 目标

- 输入：一场比赛的 `ResultData`（已在 `main.py` 中实现）。
- 输出：一个 MP4 文件（默认 1920×1080 @ 60fps），内容为数据动效。
- 可复现：同样的输入 + 主题，产出完全一致的视频。
- 可迭代：改样式不用改 Python；改分镜不用碰 HTML。
- 可扩展：后续支持批量、多语言、不同主题。

### 1.2 非目标

- 不做解说 TTS、不做字幕。
- 不做在线/实时渲染服务。
- 本期不做复杂转场（先通过每幕自身的淡入淡出解决）。

---

## 2. 总体架构

```
HLTV 页面 (main.py)
   比赛统计 + 选手统计（首杀/助攻* 后续补充）
        │
        ▼
┌─────────────┐   VideoSpec(JSON)   ┌──────────────┐   帧字节流    ┌───────────┐
│  builder.py │ ──────────────────▶ │ renderer.py  │ ────────────▶ │ encoder.py│ ─▶ out.mp4
│  分镜编排   │                     │ Playwright   │               │  ffmpeg   │
└─────────────┘                     │ 逐帧截图     │               │  NVENC    │
      ▲                             └──────────────┘               └───────────┘
      │                                    │
      │                              templates/ (HTML/CSS/JS)
      │                                    │
      └──────────── cli.py ────────────────┘

* 首杀 / 助攻：在 HLTV 详细统计页待定位后补充，见 §10.1
```

分层职责：

| 层 | 模块 | 职责 | 变更频率 |
| --- | --- | --- | --- |
| 数据层 | `main.py` | 抓取 HLTV 比赛与选手统计（首杀/助攻后续补充） | 低 |
| 编排层 | `builder.py` | `ResultData` → `VideoSpec`（分镜、时长、文案、衍生统计） | 中 |
| 表现层 | `templates/` | HTML/CSS/JS，定义每一幕的画面与动画 | 高 |
| 渲染层 | `renderer.py` | 驱动浏览器，把一幕渲染成帧序列 | 低 |
| 编码层 | `encoder.py` | 帧序列 + 可选音频 → MP4 | 低 |
| 入口层 | `cli.py` | 参数解析、流程串联、日志与进度 | 低 |

**关键设计原则**：Python 只管「时间轴与调度」，画面的所有细节（布局、颜色、动效）都在 HTML/CSS/JS 里。这样改视觉不需要重新理解 Python 代码。

---

## 3. 数据流与中间表示

### 3.1 VideoSpec

`builder.py` 输出的核心结构，也是 Python 与 JS 之间的唯一契约。

```json
{
  "version": 1,
  "meta": {
    "width": 1920,
    "height": 1080,
    "fps": 60,
    "theme": "default",
    "title": "Team A vs Team B"
  },
  "scenes": [
    {
      "id": "intro",
      "type": "intro",
      "duration": 3.0,
      "data": {
        "event": "Some Event 2025",
        "time": "2025-01-01 20:00",
        "teams": [
          { "name": "Team A", "score": 2, "won": true },
          { "name": "Team B", "score": 1, "won": false }
        ]
      }
    },
    {
      "id": "map-0",
      "type": "map_score",
      "duration": 4.0,
      "data": {
        "index": 0,
        "total": 3,
        "mapName": "Mirage",
        "rounds": 30,
        "teams": [
          { "name": "Team A", "score": 16, "won": true },
          { "name": "Team B", "score": 14, "won": false }
        ]
      }
    },
    {
      "id": "map-0-players",
      "type": "player_table",
      "duration": 6.0,
      "data": {
        "mapName": "Mirage",
        "rounds": 30,
        "players": [
          {
            "nickname": "player1",
            "team": "Team A",
            "country": "Denmark",
            "rating": 1.25,
            "kpr": 0.69,
            "openingKpr": 0.13,
            "survivalPr": 0.50,
            "adr": 85.3,
            "assistsPr": 0.11,
            "roundSwing": 2.10
          }
        ]
      }
    }
  ]
}
```

对应 Python 数据结构（`video/model.py`）：

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Scene:
    id: str
    type: str
    duration: float
    data: dict[str, Any]

@dataclass
class VideoSpec:
    width: int = 1920
    height: int = 1080
    fps: int = 60
    theme: str = "default"
    title: str = ""
    scenes: list[Scene] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return sum(s.duration for s in self.scenes)

    def to_dict(self) -> dict[str, Any]: ...
```

### 3.2 场景注册表

`type` 到模板的映射集中在一处，便于扩展：

```python
# video/scenes.py
SCENE_TYPES = {
    "intro":       "scenes/intro.html",
    "map_score":   "scenes/map_score.html",
    "player_table":"scenes/player_table.html",
    "player_board":"scenes/player_board.html",
    "outro":       "scenes/outro.html",
}
```

每个模板必须实现两个 JS 函数（见第 6 节）：`initScene(data)` 与 `renderFrame(t)`。

### 3.3 选手数据字段（每张地图 × 每名选手）

每张地图展示的选手字段及含义（均为该图内统计）：

| 展示名 | 字段 | 含义 | 计算 / 来源 | 当前可得性 |
| --- | --- | --- | --- | --- |
| Rating | `rating` | HLTV Rating 3.0 | HLTV 统计表 | ✅ 已有 |
| 场均击杀 | `kpr` | 每回合击杀 | `kills / rounds` | ✅ 可算 |
| 场均伤害 | `adr` | 每回合均伤 | HLTV ADR | ✅ 已有 |
| 场均存活 | `survivalPr` | 每回合存活率 | `(rounds - deaths) / rounds` | ✅ 可算 |
| Round Swing | `roundSwing` | 回合摇摆值 | HLTV 统计表 | ✅ 已有 |
| 场均首杀 | `openingKpr` | 每回合首杀 | 待定位 HLTV 详细统计页 | ⚠️ 后续补充抓取 |
| 场均助攻 | `assistsPr` | 每回合助攻 | 待定位 HLTV 详细统计页 | ⚠️ 后续补充抓取 |

> 命名约定：`xxxPr` 均表示 “per round”（每回合均值）。本项目中的“场均”即「每回合均值」。

**已对照 `match.html` 实测**：HLTV 比赛统计表（`table.totalstats` / `tstats` / `ctstats`）的列只有
`K-D`、`eK-eD`、`Swing`、`ADR`、`eADR`、`KAST`、`eKAST`、`Rating 3.0`，**不含首杀与助攻**。
但这些字段应在 HLTV 的其他页面上（如 “Detailed stats”），后续定位后补充解析即可（见 §10.1）。

✅ / ⚠️ 字段在数据模型里都应存在，缺失时置 `null`，模板负责优雅降级（显示 `—` 而不是报错）。

**本期范围（已定）**：先实现 ✅ 的 5 项——
**Rating / 场均击杀 / 场均伤害 / 场均存活 / Round Swing**；
⚠️ 的 `openingKpr` / `assistsPr` 字段保留在模型中但本期不填充，统一显示 `—`，
待后续（M3.5）接入 Demo 后再开启。

---

## 4. 分镜设计

一场 BO3 的默认分镜（时长可配）：

| # | type | 画面 | 默认时长 | 数据来源 |
| --- | --- | --- | --- | --- |
| 1 | `intro` | 赛事名 + 时间 + 双方队名与总比分 | 3.5s | `ResultData.event_name / match_time / team_results` |
| 每张图 | `map_score` | 图名、比分、回合数、胜方高亮 | 4.0s / 图 | `MapResultData` |
| 每张图 | `player_table` | **该图每名选手**：Rating / 场均首杀 / 场均存活 / 场均伤害 / 场均助攻 / 场均击杀 / Round Swing | 按人数动态 | `MapResultData.players` |
| 末尾前 | `player_table`（全场） | 全场汇总，可选 | 按人数动态 | `ResultData.players` |
| 末尾前 | `player_board` | 重点榜单：Rating / ADR / 首杀 / KPR 前几名 | 6.0s | 由 players 排序派生 |
| 末尾 | `outro` | 总结（总比分 / MVP / 数据来源） | 3.0s | 派生 |

> 选手数据以**每张地图**为主视角（字段见 §3.3），全场汇总作为补充镜头。
> 本期 `openingKpr` / `assistsPr` 无数据，模板显示 `—`。

衍生统计在 `builder.py` 里算好，直接塞进 `data`，让模板保持「纯展示」：

- `mvp`：全场 Rating 最高者。
- `top_rating` / `top_adr` / `top_kpr` / `top_opening`：各指标 Top N（`top_opening` 依赖 Demo）。
- `best_map`：分差最大或回合最多的一张图。
- `clutch`：Round Swing 最高者。

时长规则：`intro/outro` 固定；`map_score` 按图数；榜单类按条目数动态计算（`base + per_item * n`），保证数据多时不至于一闪而过。

---

## 5. 目录结构

```
CSResultVideoMaker/
├── main.py                     # 现有：抓取与解析（保持不动）
├── header.py
├── video/
│   ├── __init__.py
│   ├── model.py                # VideoSpec / Scene / Theme
│   ├── scenes.py               # 场景类型注册表
│   ├── builder.py              # ResultData -> VideoSpec
│   ├── renderer.py             # Playwright 逐帧渲染
│   ├── encoder.py              # ffmpeg 编码
│   └── cli.py                  # 命令行入口（python -m video.cli）
├── templates/
│   ├── base.css                # 公共样式：配色、字体、布局工具类
│   ├── base.js                 # renderFrame 工具：缓动、时间轴、数字滚动
│   ├── scenes/
│   │   ├── intro.html
│   │   ├── map_score.html
│   │   ├── player_table.html
│   │   ├── player_board.html
│   │   └── outro.html
│   ├── themes/
│   │   ├── default.json        # 颜色/字体/尺寸变量
│   │   └── dark.json
│   └── assets/
│       ├── fonts/              # 内嵌中文字体（避免环境差异）
│       └── bg/                 # 背景纹理（可选）
├── output/                     # 产物：mp4、preview、frames
├── docs/
│   ├── video-generation-research.md
│   └── video-pipeline-design.md   # 本文
├── requirements.txt
└── todo.md
```

---

## 6. 表现层设计（HTML/CSS/JS）

### 6.1 模板契约

每个场景模板是一个完整 HTML 页面，必须暴露两个全局函数：

```js
// 由 renderer 调用一次，注入本幕数据并重置状态
window.initScene = (data) => { /* ... */ };

// 由 renderer 按时间调用，t 为本幕相对时间（秒），必须幂等且确定性
window.renderFrame = (t) => { /* 只根据 t 计算画面，不依赖真实时间 */ };
```

**硬性规则**：

- 禁止使用 `requestAnimationFrame`、`setTimeout`、CSS `animation`/`transition`——所有动效必须由 `renderFrame(t)` 计算出来，否则无法逐帧复现。
- 所有网络资源本地化：字体、图片放在 `assets/`，用相对路径引用。
- 页面 `body { margin:0; overflow:hidden }`，视口即画布，避免滚动条入镜。
- 等待 `document.fonts.ready` 后再开始截图（renderer 负责）。

### 6.2 公共工具（base.js）

```js
window.clamp = (v, a, b) => Math.min(b, Math.max(a, v));
window.lerp  = (a, b, p) => a + (b - a) * p;
window.easeOutCubic = (p) => 1 - Math.pow(1 - p, 3);
window.easeInOut = (p) => p < 0.5 ? 4*p*p*p : 1 - Math.pow(-2*p+2, 3)/2;

// 在 [start, start+dur] 内把 0..1 映射到 a..b
window.prog = (t, start, dur) => window.clamp((t - start) / dur, 0, 1);

// 数字滚动：从 0 滚到 target
window.setNumber = (el, value, p, decimals = 0) => {
  el.textContent = (value * window.easeOutCubic(p)).toFixed(decimals);
};

// 全幕统一的淡入淡出（避免幕间转场）
window.fadeWrap = (el, t, duration, fade = 0.4) => {
  const inP  = window.prog(t, 0, fade);
  const outP = window.prog(t, duration - fade, fade);
  el.style.opacity = Math.min(inP, 1 - outP);
};
```

### 6.3 主题变量

`themes/default.json` 通过 CSS 自定义属性注入（renderer 读取后 `page.add_style_tag`）：

```json
{
  "bg": "#0b0f17",
  "panel": "#151c28",
  "text": "#e8edf5",
  "muted": "#8a97ab",
  "accent": "#f0b429",
  "win": "#3fb950",
  "lose": "#f85149",
  "fontFamily": "'Noto Sans SC', 'Microsoft YaHei', sans-serif",
  "headingWeight": 800
}
```

---

## 7. 渲染层设计（renderer.py）

### 7.1 基本流程

```
launch(channel="msedge" 或 "chrome")
for scene in spec.scenes:
    page.goto(file:// templates/<scene template>)
    page.evaluate("initScene", scene.data)
    page.evaluate("document.fonts.ready")     # 等字体
    frames = round(scene.duration * fps)
    for i in range(frames):
        t = i / fps
        page.evaluate("renderFrame", t)
        yield page.screenshot(type="jpeg", quality=90)
```

### 7.2 关键决策

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 浏览器 | `channel="msedge"`，失败回退 `"chrome"` | 复用系统浏览器，不下载 Chromium |
| 帧格式 | JPEG q90（默认） | 体积小、编码快；需要无损时切 PNG |
| 视口 | 等于输出分辨率，`device_scale_factor=1` | 1:1 像素，避免缩放 |
| 时间 | 虚拟时钟 `t = i / fps` | 帧精确、可复现 |
| 幕后 | 每幕独立 HTML | 隔离状态、便于并行优化与单幕预览 |
| 转场 | 幕内淡入淡出 | 避免跨幕合成复杂度 |

### 7.3 预览模式（迭代利器）

不产出完整视频，只抓取「每一幕若干关键帧」生成 PNG 缩略图组：

```
output/preview/intro_00.png
output/preview/intro_50.png
output/preview/map-0_50.png
...
```

调样式时先跑预览，秒级反馈，满意了再全量渲染。

### 7.4 代码骨架

```python
# video/renderer.py
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser
from .model import VideoSpec
from .scenes import SCENE_TYPES

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

class FrameRenderer:
    def __init__(self, spec: VideoSpec):
        self.spec = spec

    def _launch(self, p) -> Browser:
        for channel in ("msedge", "chrome"):
            try:
                return p.chromium.launch(channel=channel)
            except Exception:
                continue
        return p.chromium.launch()  # 回退到 Playwright 自带 Chromium

    def frames(self):
        with sync_playwright() as p:
            browser = self._launch(p)
            page = browser.new_page(
                viewport={"width": self.spec.width, "height": self.spec.height},
                device_scale_factor=1,
            )
            for scene in self.spec.scenes:
                html = TEMPLATES / SCENE_TYPES[scene.type]
                page.goto(html.as_uri())
                page.evaluate("(d) => window.initScene(d)", scene.data)
                page.evaluate("() => document.fonts.ready")
                total = round(scene.duration * self.spec.fps)
                for i in range(total):
                    page.evaluate("(t) => window.renderFrame(t)", i / self.spec.fps)
                    yield page.screenshot(type="jpeg", quality=90)
            browser.close()
```

> `page.evaluate` 传参要用箭头函数包裹，Playwright Python 才能正确序列化参数。

---

## 8. 编码层设计（encoder.py）

### 8.1 直接管道到 ffmpeg

不落盘帧文件，边渲染边喂给 ffmpeg，省磁盘也更快：

```python
# video/encoder.py
import subprocess

def encode(frames, out_path, fps, width, height, music=None):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "image2pipe", "-framerate", str(fps), "-vcodec", "mjpeg", "-i", "-",
    ]
    if music:
        cmd += ["-i", str(music)]
    cmd += [
        "-c:v", "h264_nvenc",
        "-preset", "p5", "-tune", "hq",
        "-rc", "vbr", "-cq", "19", "-b:v", "0",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]
    if music:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest", "-map", "0:v", "-map", "1:a"]
    cmd += [str(out_path)]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    try:
        for buf in frames:
            proc.stdin.write(buf)
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "ignore")
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg 编码失败:\n{err}")
```

### 8.2 编码参数说明

| 参数 | 值 | 说明 |
| --- | --- | --- |
| 编码器 | `h264_nvenc` | 兼容性最好；体积优先可换 `hevc_nvenc` |
| `-preset` | `p5` | NVENC 新式预设（p1 最快 … p7 最慢/最清晰） |
| `-rc vbr -cq 19` | 恒定质量 | 质量稳定，适合画面变化大的数据视频 |
| `-pix_fmt yuv420p` | 必须 | 保证 B 站/微信/QuickTime 都能播 |
| `-movflags +faststart` | 提升 | moov 前置，便于网页边下边播 |

### 8.3 无 NVENC 时的回退

```python
# 探测一次：ffmpeg -encoders | grep h264_nvenc
# 有 nvenc 用 h264_nvenc，否则回退 libx264 -crf 18 -preset slow
```

### 8.4 音频（可选）

- 只有 BGM 时：`-i bgm.mp3 -c:a aac -shortest`，建议先把 BGM 音量压到 -18dB（`-af "volume=-18dB"`）。
- 完全不要声音：命令里不加音频输入，默认即无声。

---

## 9. 入口层设计（cli.py）

```bash
# 从已解析的比赛直接出片
python -m video.cli build \
    --url "https://www.hltv.org/matches/xxxx/team-a-vs-team-b" \
    --out output/teamA_vs_teamB.mp4 \
    --fps 60 --resolution 1920x1080 \
    --theme default \
    --music assets/bgm/lofi.mp3

# 只出预览图，快速调样式
python -m video.cli preview --url "..." --out output/preview

# 只导出中间 VideoSpec（调试分镜）
python -m video.cli spec --url "..." --out output/spec.json
```

参数一览：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--url` / `--html` / `--spec` | 必选其一 | 数据来源：在线抓取 / 本地 HTML / 现成 VideoSpec |
| `--out` | `output/result.mp4` | 输出路径 |
| `--fps` | `60` | 帧率（也可 30 省时间） |
| `--resolution` | `1920x1080` | 分辨率 |
| `--theme` | `default` | 主题名 |
| `--music` | 无 | 背景音乐 |
| `--preview` | 关 | 只出预览图 |
| `--keep-frames` | 关 | 保留帧（调试） |

---

## 10. 数据接入

`builder.py` 直接复用现有解析结果：

```python
# video/builder.py
from main import ResultData, parse_match_result, parse_results, fetch
from .model import VideoSpec, Scene

def build_spec(result: ResultData, fps=60, theme="default") -> VideoSpec:
    spec = VideoSpec(fps=fps, theme=theme,
                     title=f"{result.teams[0]} vs {result.teams[1]}")
    spec.scenes.append(Scene("intro", "intro", 3.5, _intro_data(result)))
    for i, m in enumerate(result.maps):
        spec.scenes.append(Scene(f"map-{i}", "map_score", 4.0, _map_data(m, i, len(result.maps))))
        spec.scenes.append(Scene(f"map-{i}-players", "player_table",
                                 _dur(len(m.players)),
                                 _map_players_data(m)))
    spec.scenes.append(Scene("board", "player_board", 6.0, _board_data(result)))
    spec.scenes.append(Scene("outro", "outro", 3.0, _outro_data(result)))
    return spec
```

> 现状提示：`main.py` 目前不是包也没有 JSON 导出。短期用 `from main import ...` 直接调用；
> 中期建议把 `ResultData` 增加 `to_dict()/from_dict()`，并抽出 `hltv.py` 解析模块（与 todo 的「数据导出 JSON」合并推进）。

### 10.1 首杀与助攻的补充来源（待定位）

HLTV 比赛页的统计表（`table.totalstats` 等）拿不到首杀/助攻，**但 HLTV 本身很可能另有页面提供**，
不需要引入 GOTV Demo 解析。后续在 HLTV 上定位到具体字段后补进解析即可。

**已发现的线索**：

- 比赛页里有一个 “Detailed stats” 链接，指向
  `https://www.hltv.org/stats/matches/<matchId>/<teamA>-vs-<teamB>`
  （例：`/stats/matches/129805/legacy-vs-falcons`）。**优先从这里找首杀/助攻列**。
- 选手个人统计页（`/stats/players/...`）通常含 “Opening kills / Assists / Flash assists”，
  但多为**按时间/赛事聚合**，需要确认能否按单场单图拆分。

**后续动作**：

1. 打开上述详细统计页，确认首杀、助攻的列名 / DOM 结构（可能与现有 `td.kd` / `td.adr` 类似）。
2. 若为每图每选手粒度：直接在现有 `parse_player_stats_tables` 里按同样的 `td.<class>` 方式补解析。
3. 若为聚合粒度：确认 HLTV 是否提供单场/单图筛选参数，或在别的 tab（如 “Advanced”）中拆分。
4. 补进 `PlayerResultData`：新增 `first_kills` / `assists`，再换算 `openingKpr = first_kills / rounds`、
   `assistsPr = assists / rounds`。

**数据模型约定**：字段现在就保留，缺失时置 `null`，模板显示 `—`。

**备选（仅当 HLTV 确实没有）**：解析 GOTV Demo（`demoparser2`）或第三方 API（如 Leetify）。

---

## 11. 性能预算（1080p@60fps 估算）

| 环节 | 估算 | 说明 |
| --- | --- | --- |
| 单帧截图（JPEG） | 10–30 ms | 取决于画面复杂度 |
| 60s 视频 ≈ 3600 帧 | 约 1–2 分钟截图 | 主要瓶颈 |
| NVENC 编码 | 远快于实时 | 通常 < 20s |
| 内存 | 平稳 | 管道流式，不缓存全部帧 |
| 磁盘 | 仅输出 mp4 | 不落盘帧序列 |

优化手段（按需）：

- 30fps 渲染，视觉差异不大、时间减半。
- 只对变化区域频繁截图（复杂，暂不做）。
- 多进程：每幕独立进程渲染后按顺序拼接（后续可做）。

---

## 12. 错误处理与日志

- **依赖检查**：启动时校验 `ffmpeg` 是否可用、NVENC 是否存在；缺失时给明确提示（含 winget 安装命令）。
- **浏览器回退**：`msedge` → `chrome` → 内置 Chromium。
- **ffmpeg stderr**：失败时把 stderr 完整打印出来，便于定位（如参数不兼容）。
- **日志分级**：`--verbose` 打印每幕进度与帧数；默认只打关键节点。
- **中间产物**：`--keep-frames` 时把帧写到 `output/frames/` 便于逐帧排查。

---

## 13. 测试策略

| 层级 | 内容 | 方式 |
| --- | --- | --- |
| 单元 | `builder` 生成的分镜数量、时长、衍生统计正确 | pytest，纯数据 |
| 契约 | 每个模板都导出了 `initScene` / `renderFrame` | 加载后断言函数存在 |
| 快照 | 固定输入渲染关键帧，与基线图对比 | 人工/像素比对（先人工） |
| 冒烟 | 渲染 2 秒短片并验证可被 ffprobe 读取 | CI/本地脚本 |
| 端到端 | 真实 URL → mp4，检查时长/分辨率 | 手动 |

---

## 14. 实施里程碑

| 阶段 | 交付 | 验收标准 |
| --- | --- | --- |
| **M1 骨架** | `model.py` / `scenes.py` / `builder.py` / `cli.py`，只有 `intro` 一幕 | `python -m video.cli spec` 打印正确 VideoSpec |
| **M2 链路** | `renderer.py` + `encoder.py`，静态无动画 | 产出无声 MP4，内容为静态比分页 |
| **M3 数据幕** | `map_score` / `player_table` / `outro` | 覆盖一场 BO3 全部数据 |
| **M3.5 首杀/助攻**（**延后**） | 定位 HLTV 详细统计页并补充解析 `first_kills` / `assists` | 后续版本；本期只做 HLTV 的 5 项 |
| **M4 动效** | `base.js` + `renderFrame(t)` 动效（数字滚动、入场、条形图） | 画面流畅无跳变，可复现 |
| **M5 打磨** | 主题化、`player_board` 榜单、预览模式 | 换主题不改代码；预览秒级出图 |
| **M6 批量** | 多 URL 批处理、`--music`、错误处理完善 | 一条命令产出多场视频 |

与 [todo.md](../todo.md) 的对应：M1–M2 对应「渲染地图比分、选手数据」与「输出 MP4」，
M4–M5 对应「统一配色/字体/转场」，M6 对应「批量抓取」。

---

## 15. 风险与备选

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 逐帧截图慢 | 长视频耗时 | 降 fps、预览模式优先、后续多进程 |
| 字体/环境差异 | 换机画面不一致 | 内嵌字体、`document.fonts.ready` |
| HLTV 页面结构变化 | 数据解析失败 | 现有解析已做异常校验；解析与渲染解耦 |
| NVENC 不可用 | 编码失败 | 自动回退 `libx264` |
| 模板越写越乱 | 维护困难 | 强制「纯展示」+ `data` 契约，衍生逻辑留在 Python |
| 动效依赖真实时间 | 不可复现、帧错位 | 禁用 rAF/CSS 动画，只用 `renderFrame(t)` |
| HLTV 未提供首杀/助攻 | 字段长期缺失 | 字段置 `null`，模板显示 `—`；备选 GOTV Demo / 第三方 API |
| HLTV 页面结构未知 | 补充解析反复 | 待定位后按现有 `td.<class>` 模式扩展；保留回归测试 |

---

## 16. 一句话总结

**Python 编排时间轴，HTML/CSS 画每一帧，Playwright 逐帧截图，ffmpeg + NVENC 合成 MP4。**
改画面只动 `templates/`，改分镜只动 `builder.py`，改编码只动 `encoder.py`——三层解耦，互不牵制。
