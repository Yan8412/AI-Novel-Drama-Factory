from pathlib import Path

import pytest
from drama_cli.main import main


def test_cli_demo_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "demo",
                "--total-words",
                "6000",
                "--out",
                str(tmp_path),
                "--genre",
                "玄幻",
                "--license-status",
                "original",
                "-v",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "题材=玄幻" in out
    assert "版权占位=original" in out
    assert "[       video] -> [video_review]" in out
    assert "-> [done" in out
    assert "review chapter" in out
    assert "拼接清单" in out
    assert (tmp_path / next(tmp_path.iterdir()) / "episode" / "PLAY.md").is_file()


def test_cli_override_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "demo",
                "--total-words",
                "3000",
                "--out",
                str(tmp_path),
                "--override-verdict",
                "pass",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "人工覆盖" in out
    assert "need revision" not in out
