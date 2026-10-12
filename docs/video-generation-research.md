# 视频生成方案调研

> 目标：为 CS Result Video Maker 找到一条「方便、可控、可自动化」的赛果数据视频生成路径。
> 本文只做技术选型调研；定稿后的实施设计见 [video-pipeline-design.md](./video-pipeline-design.md)。

## 0. 结论速览（TL;DR）

| 方案 | 技术栈 | 上手成本 | 画面表现力 | 自动化程度 | 推荐度 |
| --- | --- | --- | --- | --- | --- |
| **HTML/CSS + Playwright 截图 + ffmpeg** | Python + Web | 低 | ★★★★★ | ★★★★★ | ⭐ **首选** |
| Remotion | React / Node | 中 | ★★★★★ | ★★★★★ | 备选（注意 License） |
| MoviePy 2.x | 纯 Python | 低 | ★★☆ | ★★★★ | 适合做「合成/混音层」 |
| Manim | Python | 高 | ★★★★ | ★★★★ | 图表动画、解释性视频 |
| matplotlib.animation | Python | 低 | ★★☆ | ★★★★ | 纯图表、最简单 |
| Motion Canvas | TypeScript | 中 | ★★★★ | ★★★★ | 喜欢 TS 且要精细动画 |
| CapCut 草稿（pyJianYingDraft） | Python + 剪映 | 低 | ★★★★★ | ★★★☆ | 想人工微调/手动发布 |
| 云 API（Shotstack 等） | HTTP | 低 | ★★★☆ | ★★★★★ | 付费、网络与合规限制 |

**建议路线**：先用 `HTML/CSS 模板 + Playwright 渲染 + ffmpeg 合成` 打通最小闭环。
本项目的视频**只呈现数据，不做解说、不需要字幕**，因此音频层可以完全跳过（最多加背景音乐），
重心全部放在画面排版与数据动效；后期若需要 React 动画组件库再考虑迁移到 Remotion。

---

## 1. 项目现状与缺口

当前 `main.py` 已能产出结构化的 `ResultData`（赛事、时间、比分、地图、选手统计），
终端表格输出只是「给人看」的临时代替。要变成视频，需要补齐三层：

1. **画面层**：把 `ResultData` 变成一帧帧图像 / 动画（比分板、地图条、选手榜）——**本项目的核心**。
2. **音频层（可选）**：仅背景音乐 / 音效；**不需要解说，也不需要字幕**。
3. **合成层**：把画面帧（必要时叠加音轨）编码成 MP4（H.264/HEVC/AV1）。

本机环境（已确认）：

- Windows + Python 3.13 虚拟环境；Node v24、npm 11 可用。
- 已安装 Chrome 与 Edge（可被 Playwright 直接复用，无需额外下载浏览器）。
- GPU：NVIDIA RTX 5060（支持 NVENC，可硬件加速 H.264/HEVC/AV1 编码）。
- **当前未安装 ffmpeg**（`ffmpeg -version` 找不到）。

---

## 2. 方案详解

### 2.1 【首选】HTML/CSS 模板 + Playwright 渲染 + ffmpeg 合成

**思路**：把一个镜头写成一个 HTML/CSS 页面，用数据 JSON 填充；用 Playwright 驱动
Chromium 把页面渲染成帧序列（或直接录制），再用 ffmpeg 拼成视频并叠加音频。

**为什么适合本项目**

- 赛果视频本质是「排版 + 数字动效」，HTML/CSS 在这方面表现力最强：
  字体、渐变、阴影、表格、条形图、Flex/Grid 布局都是现成的。
- 中文字体、emoji、图标（可用内联 SVG）几乎没有坑，比 Pillow/OpenCV 手绘省事得多。
- 复用本机已有的 Chrome/Edge，`playwright` 只装库、不一定要下载浏览器。
- 纯 Python 侧控制时间轴，和现有 `main.py` 无缝衔接。

**安装**

```bash
# 1) ffmpeg（推荐 winget，选 Gyan.FFmpeg 完整版）
winget install Gyan.FFmpeg
# 2) Python 渲染依赖
.venv/Scripts/pip install playwright
# 若不想下载 Chromium，可直接用系统已装的 Edge/Chrome（见下方代码）
```

**帧渲染的三种做法**

| 做法 | 说明 | 适用 |
| --- | --- | --- |
| 逐帧截图 | 每帧 `page.evaluate` 设置时间 → `page.screenshot()` | 帧数少、画面复杂、需要确定性 |
| CSS/JS 动画 + 定时截图 | 页面自身动画，隔固定时间截图 | 简单、但不保证帧精确 |
| 浏览器内 WebCodecs 编码 | 在页面里直接编码帧，导出视频流 | 性能最优，复杂度偏高 |

对赛果视频（通常 30~90 秒、30/60fps），**逐帧截图**最稳妥：
可以用一个全局 `renderFrame(t)` 函数，让页面在给定时间点渲染出确定画面，避免动画时序漂移。

**最小代码骨架**

```python
# render.py —— 把 ResultData 渲染成帧序列
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

FPS = 60
DURATION = 30  # 秒

def render(result, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.dumps(result_as_dict(result), ensure_ascii=False)
    with sync_playwright() as p:
        # channel="msedge" 或 "chrome"：复用系统浏览器
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto((Path("templates") / "scoreboard.html").resolve().as_uri())
        page.evaluate("d => window.initScene(d)", json.loads(data))
        for i in range(FPS * DURATION):
            t = i / FPS
            page.evaluate("t => window.renderFrame(t)", t)
            page.screenshot(path=str(out_dir / f"frame_{i:05d}.png"))
        browser.close()
```

```bash
# 合成：帧序列 → MP4（纯画面，NVENC 硬件编码）
ffmpeg -y -framerate 60 -i frames/frame_%05d.png \
  -c:v h264_nvenc -pix_fmt yuv420p -an out.mp4

# 若加背景音乐：把 -an 换成 -i bgm.mp3 -c:a aac -shortest
```

**注意点**

- 截图保存为 PNG 体积大，可改输出 JPEG（`quality=90`）或渲染后直接管道给 ffmpeg。
- 逐帧截图速度取决于画面复杂度，1080p 一般每秒几十帧，分钟级视频可接受。
- 需要固定「虚拟时钟」：所有动画由 `renderFrame(t)` 驱动，而不是依赖 `requestAnimationFrame`。

### 2.2 Remotion（React 写视频）

- **定位**：用 React 组件描述视频，`<Series>`、`spring()`、`interpolate()` 做动画，
  自带渲染器（headless Chrome + bundled ffmpeg），有 Studio 可视化预览、Lambda 云端渲染。
- **优点**：动画 API 极其顺手，生态和模板多，非常适合「数据驱动 + 参数化」的批量视频。
- **缺点 / 风险**：
  - 引入 Node/React 技术栈，与现有 Python 项目是两套工程。
  - **License 需注意**：Remotion 对个人和 ≤3 人的公司免费；超过 3 人需购买 Company License
    （automator 场景 $0.01/render，最低 $100/月）。
- **结论**：如果以后要做「批量、参数化、强动效」的视频产品，值得迁移；当前阶段略重。

### 2.3 MoviePy 2.x（纯 Python 合成）

- **定位**：Python 版「视频剪辑库」，做 Clip 拼接、叠加文字、音轨混合、导出。
- **优点**：全 Python，和现有数据流同语言；2.x 重写了 API，性能有改善；
  `imageio-ffmpeg` 会附带 ffmpeg 二进制，可减少环境依赖。
- **缺点**：复杂排版和动效要手写，文字渲染依赖 Pillow，中文字体要手动指定；
  不适合做精致的运动图形。
- **最佳用法**：**只把它当混音/合成层**——输入已经渲染好的帧序列或片段（+ 可选背景音乐），
  做最终的剪辑与导出；画面仍交给 HTML 或 matplotlib。

### 2.4 Manim（解释性动画）

- **定位**：3Blue1Brown 那类数学/数据动画，擅长「数字滚动、坐标轴、图表生长」。
- **优点**：动画质感高级，适合做「选手 Rating 排名变化」「地图控图趋势」这类解释镜头。
- **缺点**：学习曲线陡，渲染慢（每帧调 Python），做表格排版很别扭，需要 ffmpeg（LaTeX 可选）。
- **结论**：适合做少量「点睛」动画片段，不建议作为整条视频的渲染主引擎。

### 2.5 matplotlib / plotly 动画

- **定位**：把图表做成动画（`FuncAnimation` / plotly + kaleido 导帧）。
- **优点**：数据可视化最快，和 pandas/numpy 无缝。
- **缺点**：只能做图表，无法做比分板、队伍 Logo 等版面元素。
- **结论**：可作为 HTML 方案中的「图表素材生成器」，或纯数据向视频的轻量选择。

### 2.6 Motion Canvas（TS 动画）

- 用 TypeScript 写「生成器式」时间轴，编辑器可视化强，适合教程/解释类视频。
- 需要 Node + TS 基础，生态比 Remotion 小，中文资料少。作为 Remotion 的同类备选。

### 2.7 CapCut 草稿生成（pyJianYingDraft）

- 用 Python 生成「剪映」工程草稿文件，用户打开剪映即可预览、微调、导出。
- **优点**：剪映免费、模板/转场/字幕能力成熟，中文支持好；自动化 + 人工精修结合。
- **缺点**：依赖剪映客户端与草稿格式（可能随版本变化），无法完全无人值守。
- **结论**：适合「脚本先生成初剪，人工润色后发布」的半自动流程。

### 2.8 云 API（Shotstack / Creatomate / JSON2Video 等）

- 提交一份 JSON 时间轴 + 素材 URL，云端返回 MP4。
- **优点**：无需本地环境，天然可扩展。
- **缺点**：付费、上传数据到第三方、中文 TTS/字体支持参差、受网络影响。
- **结论**：本项目以本地数据为主，暂不考虑。

---

## 3. 音频（可选，本方案可跳过）

本项目的视频**只呈现数据，不需要字幕**，也不需要解说。
因此音频层可以完全不做；若想加点氛围，仅叠加背景音乐即可。

| 需求 | 推荐 | 说明 |
| --- | --- | --- |
| 背景音乐 / 音效 | 免费素材库 + ffmpeg `amix` | 音量控制在 -18dB 左右，别盖住画面重点。 |
| （仅将来可选）解说 TTS | edge-tts / Azure Speech | 若以后真想做解说向视频再考虑；`edge-tts` 免费但需联网。 |

> 因为不做字幕，无需 TTS 词级时间戳，也无需 whisper 对齐，音频链路大幅简化；
> 甚至可以完全不加音轨（ffmpeg `-an`）输出纯画面版本。

---

## 4. 编码与合成建议

- **安装**：`winget install Gyan.FFmpeg`（含各编解码器，装完把 `bin` 加进 PATH）。
- **编码器**：RTX 5060 支持 NVENC，可用 `h264_nvenc` / `hevc_nvenc` / `av1_nvenc` 硬件加速；
  兼容性优先选 `h264_nvenc`，追求体积选 `hevc_nvenc`（B 站/YouTube 均支持）。
- **统一参数**：`-pix_fmt yuv420p`、`-r 60`、`-c:a aac -b:a 192k`，避免平台转码异常。
- **音量处理**：若加 BGM，用 `amix` 混合并压到 -18dB 左右；纯数据视频可直接 `-an` 输出无音轨版本。
- **确定性**：所有素材、字体、时间轴以 JSON 描述，保证同样输入产出同样视频。

---

## 5. 落地路线建议

**阶段一（最小闭环，1~2 天）**

1. `winget install Gyan.FFmpeg`，装 `playwright`。
2. 写一个 `templates/scoreboard.html`：静态渲染单场比赛比分行。
3. `render.py` 用 Playwright 逐帧截图，`ffmpeg` 合成无声 MP4（先不做动画）。

**阶段二（数据动效）**

4. 在模板里加 `renderFrame(t)`：比分滚动、条状图生长、选手榜逐个入场。
5. 按场景拆分镜（开场 / 地图比分 / 选手榜 / 结尾），用 JSON 描述时间轴。

**阶段三（观感打磨）**

6. 统一配色、字体、转场；可选叠加背景音乐（也可 `-an` 输出纯画面版本）。
7. 调整节奏与停留时间，让数据看得清、重点有停顿。

**阶段四（工程化）**

8. 批量抓取 → 一条命令产出多场比赛视频。
9. 可选：若动效需求变重，评估迁移 Remotion。

---

## 6. 参考链接

- Playwright Python: <https://playwright.dev/python/docs/videos>
- Remotion License & Pricing: <https://www.remotion.dev/docs/license> · <https://www.remotion.pro/license>
- MoviePy: <https://zulko.github.io/moviepy/>
- Manim: <https://docs.manim.community/>
- Motion Canvas: <https://motioncanvas.io/>
- edge-tts（可选，仅将来做解说时）: <https://github.com/rany2/edge-tts>
- pyJianYingDraft: <https://github.com/GuanYixuan/pyJianYingDraft>
- ffmpeg 下载: <https://www.gyan.dev/ffmpeg/builds/>
