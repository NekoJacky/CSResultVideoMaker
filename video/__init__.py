"""CS Result Video Maker —— 视频生成流水线。

分层：
    builder  -> 把 ResultData 编排成 VideoSpec（分镜）
    renderer -> 用 Playwright 把每一幕渲染成帧序列
    encoder  -> 用 ffmpeg 把帧序列编码成 MP4

设计文档见 docs/video-pipeline-design.md。
"""

__all__ = ["model", "scenes", "builder", "cli"]
