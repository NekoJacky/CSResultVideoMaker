"""命令行入口：``python -m video.cli <spec|preview|build>``。

- ``spec``：把比赛解析结果导出为 VideoSpec JSON（分镜调试用）。
- ``build``：渲染 + 编码，产出无声 MP4（M2）。
- ``preview``：关键帧预览（M5，暂未实现）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from main import ResultData, fetch, parse_match_result

from .builder import build_spec
from .encoder import encode
from .renderer import render_frames


def _load_result(args: argparse.Namespace) -> ResultData:
    if args.html:
        html = Path(args.html).read_text(encoding="utf-8")
        return parse_match_result(html)
    if args.url:
        return parse_match_result(fetch(args.url))
    raise SystemExit("需要提供数据来源：--html <本地比赛页> 或 --url <HLTV 比赛页>")


def _parse_resolution(value: str) -> tuple[int, int]:
    try:
        width, height = value.lower().split("x", 1)
        return int(width), int(height)
    except (ValueError, AttributeError) as exc:
        raise SystemExit(
            f"无效的分辨率: {value!r}（应为 1920x1080 形式）"
        ) from exc


def _cmd_spec(args: argparse.Namespace) -> int:
    result = _load_result(args)
    width, height = _parse_resolution(args.resolution)
    spec = build_spec(
        result,
        width=width,
        height=height,
        fps=args.fps,
        theme=args.theme,
    )
    text = spec.to_json()
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(
            f"已写入 {args.out}"
            f"（{len(spec.scenes)} 幕 / {spec.total_duration:.1f}s / "
            f"{spec.total_frames} 帧 @ {spec.fps}fps）"
        )
    else:
        print(text)
    return 0


def _cmd_preview(args: argparse.Namespace) -> int:
    print("preview 将在 M5 实现（渲染每幕关键帧 PNG）")
    return 1


def _cmd_build(args: argparse.Namespace) -> int:
    result = _load_result(args)
    width, height = _parse_resolution(args.resolution)
    spec = build_spec(
        result,
        width=width,
        height=height,
        fps=args.fps,
        theme=args.theme,
    )
    frames = render_frames(spec)
    encode(
        frames,
        args.out,
        fps=spec.fps,
        width=spec.width,
        height=spec.height,
        music=args.music,
    )
    print(
        f"已生成 {args.out}"
        f"（{len(spec.scenes)} 幕 / {spec.total_duration:.1f}s / "
        f"{spec.total_frames} 帧 @ {spec.fps}fps）"
    )
    return 0


def _add_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--html", help="本地比赛页 HTML 路径")
    parser.add_argument("--url", help="HLTV 比赛页 URL")
    parser.add_argument("--fps", type=int, default=60, help="帧率（默认 60）")
    parser.add_argument(
        "--resolution",
        default="1920x1080",
        help="输出分辨率（默认 1920x1080）",
    )
    parser.add_argument("--theme", default="default", help="主题名（默认 default）")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m video.cli",
        description="CS 赛果数据视频生成",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_spec = sub.add_parser("spec", help="导出 VideoSpec JSON（分镜调试）")
    _add_data_args(p_spec)
    p_spec.add_argument("--out", help="输出路径（缺省打印到 stdout）")
    p_spec.set_defaults(func=_cmd_spec)

    p_preview = sub.add_parser("preview", help="渲染关键帧预览 PNG（M5）")
    _add_data_args(p_preview)
    p_preview.add_argument("--out", default="output/preview")
    p_preview.set_defaults(func=_cmd_preview)

    p_build = sub.add_parser("build", help="渲染并编码为 MP4（M2）")
    _add_data_args(p_build)
    p_build.add_argument("--out", default="output/result.mp4")
    p_build.add_argument("--music", help="背景音乐路径（可选）")
    p_build.set_defaults(func=_cmd_build)

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
