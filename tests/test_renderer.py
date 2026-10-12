"""``video.renderer`` 渲染层 + 模板契约测试。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from video import encoder
from video.model import Scene, VideoSpec
from video.renderer import (
    ROOT,
    TEMPLATES,
    load_theme,
    render_frames,
    theme_css,
)
from video.scenes import SCENE_TYPES


def test_load_theme_default_fallback():
    assert load_theme("default")["bg"] == "#0b0f17"
    # 不存在的主题回退 default
    assert load_theme("does-not-exist")["bg"] == "#0b0f17"


def test_theme_css_contains_variables():
    css = theme_css("default")

    assert css.startswith(":root {")
    assert "--bg:" in css
    assert "--accent:" in css
    assert "--font-family:" in css


def test_templates_dir_is_under_project_root():
    assert TEMPLATES.is_dir()
    assert (TEMPLATES / "base.css").exists()
    assert (TEMPLATES / "base.js").exists()


@pytest.mark.parametrize("scene_type", sorted(SCENE_TYPES))
def test_template_contract(scene_type):
    """每个场景模板都必须导出 initScene / renderFrame（契约）。"""
    html = (TEMPLATES / SCENE_TYPES[scene_type]).read_text(encoding="utf-8")

    assert "window.initScene" in html
    assert "window.renderFrame" in html
    assert "base.css" in html
    assert "base.js" in html


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="需要系统级 ffmpeg"
)
def test_render_and_encode_smoke(tmp_path):
    """渲染 2s 短片并验证可被 ffprobe 读取（冒烟测试）。"""
    spec = VideoSpec(width=320, height=180, fps=10, theme="default", title="smoke")
    spec.add(
        Scene(
            "intro",
            "intro",
            0.2,
            {
                "event": "Smoke Cup",
                "time": "2026-01-01 00:00",
                "totalRounds": 2,
                "mapCount": 1,
                "teams": [
                    {"name": "A", "score": 1, "won": True},
                    {"name": "B", "score": 0, "won": False},
                ],
            },
        )
    )

    try:
        frames = list(render_frames(spec))
    except RuntimeError as exc:
        pytest.skip(f"浏览器不可用：{exc}")

    assert len(frames) == 2  # 0.2s * 10fps
    for frame in frames:
        assert frame[:2] == b"\xff\xd8"  # JPEG 魔数

    out = tmp_path / "smoke.mp4"
    encoder.encode(
        frames, out, fps=spec.fps, width=spec.width, height=spec.height
    )

    assert out.exists() and out.stat().st_size > 0

    if shutil.which("ffprobe") is None:
        pytest.skip("需要 ffprobe 验证输出")

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr
    assert float(probe.stdout.strip()) > 0
