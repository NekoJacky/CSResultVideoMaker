"""``video.model`` 单元测试。"""

from __future__ import annotations

import json

from video.model import SPEC_VERSION, Scene, VideoSpec


def test_empty_spec():
    spec = VideoSpec()
    assert spec.scenes == []
    assert spec.total_duration == 0
    assert spec.total_frames == 0


def test_add_is_chainable_and_accumulates():
    spec = VideoSpec(fps=30)
    result = spec.add(Scene("a", "intro", 2.0, {}))
    spec.add(Scene("b", "outro", 1.5, {}))

    assert result is spec
    assert spec.total_duration == 3.5
    assert spec.total_frames == round(3.5 * 30)


def test_to_dict_meta_and_scenes():
    spec = VideoSpec(width=1280, height=720, fps=60, theme="dark", title="标题")
    spec.add(Scene("intro", "intro", 1.0, {"k": "v"}))

    data = spec.to_dict()

    assert data["version"] == SPEC_VERSION
    assert data["meta"] == {
        "width": 1280,
        "height": 720,
        "fps": 60,
        "theme": "dark",
        "title": "标题",
        "totalDuration": 1.0,
        "totalFrames": 60,
    }
    assert data["scenes"] == [
        {"id": "intro", "type": "intro", "duration": 1.0, "data": {"k": "v"}}
    ]


def test_to_json_keeps_unicode():
    spec = VideoSpec(title="中文标题")
    text = spec.to_json()

    assert "中文标题" in text
    assert json.loads(text)["meta"]["title"] == "中文标题"


def test_scene_duration_is_rounded():
    assert Scene("a", "intro", 1.23456, {}).to_dict()["duration"] == 1.235
