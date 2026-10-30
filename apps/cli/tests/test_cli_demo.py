from pathlib import Path

import pytest
from drama_cli.main import main


def test_cli_demo_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--total-words", "6000", "--out", str(tmp_path), "-v"]) == 0
    out = capsys.readouterr().out
    assert "[       video] -> [video_review]" in out
    assert "-> [done" in out
    assert "review chapter" in out
