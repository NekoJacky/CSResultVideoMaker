"""``video.scenes`` 场景注册表测试。"""

from __future__ import annotations

import pytest

from video.scenes import SCENE_TYPES, template_for


def test_known_types_return_template_path():
    assert template_for("intro") == "scenes/intro.html"
    for scene_type in SCENE_TYPES:
        assert template_for(scene_type).endswith(".html")


def test_unknown_type_raises():
    with pytest.raises(ValueError) as exc:
        template_for("does-not-exist")
    assert "does-not-exist" in str(exc.value)
