"""视频规格的数据结构。

VideoSpec 是 Python 与前端模板（HTML/JS）之间的唯一契约，
序列化后交给渲染层，模板按 ``scene.type`` 选择对应 HTML。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

SPEC_VERSION = 1


@dataclass
class Scene:
    """一个镜头（一幕）。"""

    id: str
    type: str
    duration: float
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "duration": round(self.duration, 3),
            "data": self.data,
        }


@dataclass
class VideoSpec:
    """整条视频的规格。"""

    width: int = 1920
    height: int = 1080
    fps: int = 60
    theme: str = "default"
    title: str = ""
    scenes: list[Scene] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return sum(scene.duration for scene in self.scenes)

    @property
    def total_frames(self) -> int:
        return round(self.total_duration * self.fps)

    def add(self, scene: Scene) -> VideoSpec:
        """链式追加一幕。"""
        self.scenes.append(scene)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SPEC_VERSION,
            "meta": {
                "width": self.width,
                "height": self.height,
                "fps": self.fps,
                "theme": self.theme,
                "title": self.title,
                "totalDuration": round(self.total_duration, 3),
                "totalFrames": self.total_frames,
            },
            "scenes": [scene.to_dict() for scene in self.scenes],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
