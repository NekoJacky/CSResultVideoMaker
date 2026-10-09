"""``video.cli`` 命令行测试。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from video import cli

ROOT = Path(__file__).resolve().parent.parent


def test_load_result_requires_a_source():
    args = SimpleNamespace(html=None, url=None)
    with pytest.raises(SystemExit):
        cli._load_result(args)


def test_spec_prints_json_to_stdout(sample_result, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_load_result", lambda args: sample_result)

    assert cli.main(["spec"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["meta"]["title"] == "Alpha vs Bravo"
    assert data["scenes"][0]["type"] == "intro"


def test_spec_writes_file(sample_result, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_load_result", lambda args: sample_result)
    out = tmp_path / "nested" / "spec.json"

    assert cli.main(["spec", "--out", str(out)]) == 0

    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["scenes"]) == 7


def test_preview_and_build_are_stubs(sample_result, monkeypatch):
    monkeypatch.setattr(cli, "_load_result", lambda args: sample_result)

    assert cli.main(["preview"]) == 1
    assert cli.main(["build"]) == 1


@pytest.mark.skipif(
    not (ROOT / "match.html").exists(),
    reason="需要本地 match.html（真实比赛页样本）",
)
def test_spec_with_real_match_html(tmp_path):
    out = tmp_path / "spec.json"

    assert cli.main(["spec", "--html", str(ROOT / "match.html"), "--out", str(out)]) == 0

    data = json.loads(out.read_text(encoding="utf-8"))
    types = [scene["type"] for scene in data["scenes"]]
    assert types[0] == "intro"
    assert types[-1] == "outro"
    assert "player_table" in types
    assert data["meta"]["totalFrames"] > 0
