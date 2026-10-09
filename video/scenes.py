"""场景类型注册表：``type`` -> 模板文件的相对路径。"""

from __future__ import annotations

# 相对 templates/ 目录
SCENE_TYPES: dict[str, str] = {
    "intro": "scenes/intro.html",
    "map_score": "scenes/map_score.html",
    "player_table": "scenes/player_table.html",
    "player_board": "scenes/player_board.html",
    "outro": "scenes/outro.html",
}


def template_for(scene_type: str) -> str:
    """返回场景类型对应的模板路径，未知类型直接报错。"""
    try:
        return SCENE_TYPES[scene_type]
    except KeyError as exc:
        known = ", ".join(sorted(SCENE_TYPES))
        raise ValueError(
            f"未知的场景类型: {scene_type!r}（可用: {known}）"
        ) from exc
