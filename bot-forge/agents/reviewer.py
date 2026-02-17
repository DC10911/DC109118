"""Reviewer agent: static analysis and structure validation."""

from __future__ import annotations

import logging
from pathlib import Path

from core.models import ReviewReport

logger = logging.getLogger("botforge.reviewer")

REQUIRED_FILES = {"main.py", "README.md", "requirements.txt"}
BANNED_PATTERNS = [
    "eval(",
    "exec(",
    "__import__(",
    "subprocess.call(",
    "os.system(",
]


def review_project(project_dir: Path) -> ReviewReport:
    """Perform structural and basic security review."""
    issues: list[str] = []
    warnings: list[str] = []

    # Check required files exist
    for fname in REQUIRED_FILES:
        if not (project_dir / fname).exists():
            issues.append(f"Missing required file: {fname}")

    # Check for banned patterns in Python files
    for py_file in project_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="replace")
        for pattern in BANNED_PATTERNS:
            if pattern in content:
                warnings.append(f"Potentially unsafe pattern '{pattern}' in {py_file.name}")

    # Check README is not empty
    readme = project_dir / "README.md"
    if readme.exists() and readme.stat().st_size < 20:
        warnings.append("README.md appears to be too short")

    # Check requirements.txt is not empty
    reqs = project_dir / "requirements.txt"
    if reqs.exists() and reqs.stat().st_size == 0:
        warnings.append("requirements.txt is empty")

    passed = len(issues) == 0
    logger.info("Review %s: %d issues, %d warnings", "PASSED" if passed else "FAILED", len(issues), len(warnings))

    return ReviewReport(passed=passed, issues=issues, warnings=warnings)
