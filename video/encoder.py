"""编码层：把 JPEG 帧字节流管道编码成 MP4。

设计见 docs/video-pipeline-design.md §8。

- 优先 ``h264_nvenc``，探测不到则回退 ``libx264``。
- 边渲染边喂给 ffmpeg，不落盘中间帧。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path is None:
        raise RuntimeError(
            "未找到 ffmpeg，请先安装：winget install Gyan.FFmpeg"
        )
    return path


def detect_encoder() -> str:
    """探测可用的 H.264 编码器，优先 NVENC。"""
    proc = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        errors="ignore",
    )
    if proc.returncode != 0:
        return "libx264"
    output = proc.stdout + proc.stderr
    return "h264_nvenc" if "h264_nvenc" in output else "libx264"


def build_command(
    out_path: str | Path,
    *,
    fps: int,
    width: int,
    height: int,
    encoder: str,
    music: str | Path | None = None,
) -> list[str]:
    """构造 ffmpeg 命令（纯函数，便于测试）。"""
    cmd = [
        _ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(fps),
        "-vcodec",
        "mjpeg",
        "-i",
        "-",
    ]
    if music:
        cmd += ["-i", str(music)]

    # 统一缩放到目标分辨率并转为 tv-range 的 yuv420p，
    # 避免 JPEG（full-range）带入 yuvj420p 导致播放器兼容问题。
    cmd += ["-vf", f"scale={width}:{height},format=yuv420p"]

    if encoder == "h264_nvenc":
        cmd += [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p5",
            "-tune",
            "hq",
            "-rc",
            "vbr",
            "-cq",
            "19",
            "-b:v",
            "0",
        ]
    else:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18"]

    cmd += [
        "-pix_fmt",
        "yuv420p",
        "-color_range",
        "tv",
        "-movflags",
        "+faststart",
    ]

    if music:
        cmd += [
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-af",
            "volume=-18dB",
            "-shortest",
            "-map",
            "0:v",
            "-map",
            "1:a",
        ]

    cmd += [str(out_path)]
    return cmd


def encode(
    frames: Iterable[bytes],
    out_path: str | Path,
    *,
    fps: int,
    width: int,
    height: int,
    music: str | Path | None = None,
) -> None:
    """把帧字节流编码为 MP4。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    encoder = detect_encoder()
    cmd = build_command(
        out_path,
        fps=fps,
        width=width,
        height=height,
        encoder=encoder,
        music=music,
    )

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    stream_error: Exception | None = None
    try:
        for frame in frames:
            proc.stdin.write(frame)
    except BrokenPipeError:
        # ffmpeg 提前退出，具体原因在 returncode / stderr 中报告。
        pass
    except Exception as exc:  # noqa: BLE001 - 渲染流中断也要做清理
        stream_error = exc
    finally:
        try:
            proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass

    err = proc.stderr.read().decode("utf-8", "ignore")
    code = proc.wait()

    if stream_error is not None:
        raise RuntimeError(f"渲染帧流中断：{stream_error}") from stream_error
    if code != 0:
        raise RuntimeError(f"ffmpeg 编码失败（{encoder}）：\n{err}")
