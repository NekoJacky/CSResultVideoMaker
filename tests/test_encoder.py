"""``video.encoder`` 编码层测试。"""

from __future__ import annotations

import shutil

import pytest

from video import encoder


def test_detect_encoder_returns_known_value():
    enc = encoder.detect_encoder()
    assert enc in ("h264_nvenc", "libx264")


def test_build_command_nvenc_silent(monkeypatch):
    monkeypatch.setattr(encoder, "_ffmpeg", lambda: "ffmpeg")

    cmd = encoder.build_command(
        "out.mp4", fps=60, width=1920, height=1080, encoder="h264_nvenc"
    )

    assert cmd[0] == "ffmpeg"
    assert "h264_nvenc" in cmd
    assert "-pix_fmt" in cmd and "yuv420p" in cmd
    assert "-color_range" in cmd and "tv" in cmd
    assert any("format=yuv420p" in arg for arg in cmd)  # 强制 tv-range
    assert "out.mp4" == cmd[-1]
    # 无声：不引入第二路输入，也不带音频编码参数
    assert "-i" in cmd
    assert cmd.count("-i") == 1
    assert "-c:a" not in cmd


def test_build_command_libx264_fallback(monkeypatch):
    monkeypatch.setattr(encoder, "_ffmpeg", lambda: "ffmpeg")

    cmd = encoder.build_command(
        "out.mp4", fps=30, width=1280, height=720, encoder="libx264"
    )

    assert "libx264" in cmd
    assert "-crf" in cmd and "18" in cmd
    assert "h264_nvenc" not in cmd


def test_build_command_with_music(monkeypatch):
    monkeypatch.setattr(encoder, "_ffmpeg", lambda: "ffmpeg")

    cmd = encoder.build_command(
        "out.mp4",
        fps=60,
        width=1920,
        height=1080,
        encoder="h264_nvenc",
        music="bgm.mp3",
    )

    assert cmd.count("-i") == 2
    assert "bgm.mp3" in cmd
    assert "aac" in cmd
    assert "-map" in cmd and "0:v" in cmd and "1:a" in cmd


def test_missing_ffmpeg_raises(monkeypatch):
    monkeypatch.setattr(encoder.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError) as exc:
        encoder._ffmpeg()
    assert "ffmpeg" in str(exc.value)
