"""渲染层：用 Playwright 把 ``VideoSpec`` 渲染成 JPEG 帧字节流。

设计见 docs/video-pipeline-design.md §7。

- 浏览器优先复用系统 Edge/Chrome，最后回退 Playwright 内置 Chromium。
- 每幕独立 HTML，注入主题 CSS 变量后调用 ``initScene(data)``。
- 逐帧调用 ``renderFrame(t)``，虚拟时钟保证可复现。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Page, sync_playwright

from .model import VideoSpec
from .scenes import template_for

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
THEMES = TEMPLATES / "themes"

JPEG_QUALITY = 90

# 主题 JSON 字段 -> CSS 自定义属性名
_THEME_CSS_VARS = {
    "bg": "--bg",
    "panel": "--panel",
    "text": "--text",
    "muted": "--muted",
    "accent": "--accent",
    "win": "--win",
    "lose": "--lose",
    "fontFamily": "--font-family",
    "headingWeight": "--heading-weight",
}


def load_theme(theme: str) -> dict[str, str]:
    """读取主题 JSON；找不到时回退 default，仍找不到返回空字典。"""
    path = THEMES / f"{theme}.json"
    if not path.exists():
        path = THEMES / "default.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def theme_css(theme: str) -> str:
    """把主题 JSON 转成 ``:root { --x: ...; }`` 的 CSS 片段。"""
    values = load_theme(theme)
    declarations = []
    for key, var_name in _THEME_CSS_VARS.items():
        if key in values:
            declarations.append(f"  {var_name}: {values[key]};")
    if not declarations:
        return ""
    return ":root {\n" + "\n".join(declarations) + "\n}"


class FrameRenderer:
    """驱动浏览器，把一幕渲染成帧序列。"""

    def __init__(self, spec: VideoSpec):
        self.spec = spec

    def _launch(self, playwright):
        errors: list[str] = []
        for channel in ("msedge", "chrome"):
            try:
                return playwright.chromium.launch(channel=channel, headless=True)
            except Exception as exc:  # noqa: BLE001 - 逐级回退
                errors.append(f"{channel}: {exc}")
        try:
            return playwright.chromium.launch(headless=True)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"bundled chromium: {exc}")
        raise RuntimeError(
            "无法启动 Chromium 浏览器（已尝试 msedge / chrome / 内置 Chromium）：\n"
            + "\n".join(errors)
        )

    def _inject_theme(self, page: Page) -> None:
        css = theme_css(self.spec.theme)
        if css:
            page.add_style_tag(content=css)

    def frames(self) -> Iterator[bytes]:
        """逐帧产出 JPEG 字节（懒执行，供 encoder 流式消费）。"""
        with sync_playwright() as playwright:
            browser = self._launch(playwright)
            try:
                page = browser.new_page(
                    viewport={"width": self.spec.width, "height": self.spec.height},
                    device_scale_factor=1,
                )
                for scene in self.spec.scenes:
                    html = TEMPLATES / template_for(scene.type)
                    page.goto(html.as_uri(), wait_until="load")
                    self._inject_theme(page)
                    page.evaluate("(d) => window.initScene(d)", scene.data)
                    page.evaluate("() => document.fonts.ready.then(() => true)")
                    total = max(1, round(scene.duration * self.spec.fps))
                    for index in range(total):
                        page.evaluate(
                            "(t) => window.renderFrame(t)",
                            index / self.spec.fps,
                        )
                        yield page.screenshot(type="jpeg", quality=JPEG_QUALITY)
            finally:
                browser.close()


def render_frames(spec: VideoSpec) -> Iterator[bytes]:
    """模块级入口：返回帧字节流生成器。"""
    return FrameRenderer(spec).frames()
