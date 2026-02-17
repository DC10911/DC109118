"""Unit tests for the reviewer agent."""

import tempfile
from pathlib import Path

from agents.reviewer import review_project


def test_review_pass():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "main.py").write_text("print('hello')\n")
        (p / "README.md").write_text("# My Bot\n\nDescription here.\n")
        (p / "requirements.txt").write_text("click>=8.0\n")

        report = review_project(p)
        assert report.passed is True
        assert len(report.issues) == 0


def test_review_missing_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        # No files at all
        report = review_project(p)
        assert report.passed is False
        assert len(report.issues) >= 3  # missing main.py, README.md, requirements.txt


def test_review_warns_on_unsafe_code():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "main.py").write_text("eval('1+1')\n")
        (p / "README.md").write_text("# Bot\n\nDescription text.\n")
        (p / "requirements.txt").write_text("something\n")

        report = review_project(p)
        assert len(report.warnings) > 0
        assert any("eval(" in w for w in report.warnings)
