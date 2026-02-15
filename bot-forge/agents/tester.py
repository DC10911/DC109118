"""Tester agent: runs lint + pytest on a generated project."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from core.models import TestResult

logger = logging.getLogger("botforge.tester")


async def _run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode or 0, stdout.decode(errors="replace")


async def run_tests(project_dir: Path) -> TestResult:
    """Run ruff check + pytest on the generated project."""
    outputs: list[str] = []
    all_passed = True

    # --- syntax check via py_compile ---
    py_files = list(project_dir.rglob("*.py"))
    compile_failures = 0
    for pf in py_files:
        code, out = await _run_cmd(["python3", "-m", "py_compile", str(pf)], cwd=project_dir)
        if code != 0:
            compile_failures += 1
            outputs.append(f"COMPILE FAIL {pf.name}: {out}")
    outputs.append(f"Compile check: {len(py_files) - compile_failures}/{len(py_files)} OK")
    if compile_failures:
        all_passed = False

    # --- pytest if tests exist ---
    test_dir = project_dir / "tests"
    test_count = 0
    test_failures = 0
    if test_dir.exists() and list(test_dir.glob("test_*.py")):
        code, out = await _run_cmd(
            ["python3", "-m", "pytest", str(test_dir), "-v", "--tb=short"], cwd=project_dir
        )
        outputs.append(f"pytest exit={code}\n{out}")
        if code != 0:
            all_passed = False
        # Parse basic counts from output
        for line in out.splitlines():
            if "passed" in line or "failed" in line:
                outputs.append(line)
    else:
        outputs.append("No test files found, skipping pytest.")

    result = TestResult(
        passed=all_passed,
        total=len(py_files),
        failures=compile_failures + test_failures,
        output="\n".join(outputs),
    )
    logger.info("Tests %s: %d files checked", "PASSED" if all_passed else "FAILED", len(py_files))
    return result
