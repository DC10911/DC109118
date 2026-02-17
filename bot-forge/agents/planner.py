"""Planner agent: converts a validated BotSpec into a ProjectPlan."""

from __future__ import annotations

import logging

from core.models import BotSpec, Platform, ProjectPlan

logger = logging.getLogger("botforge.planner")

# Maps platform → additional pip dependencies
PLATFORM_DEPS: dict[Platform, list[str]] = {
    Platform.TELEGRAM: ["python-telegram-bot>=20.7"],
    Platform.DISCORD: ["discord.py>=2.3.0"],
    Platform.SLACK: ["slack-bolt>=1.18.0"],
    Platform.CLI: ["click>=8.1.7"],
    Platform.WEB_API: ["fastapi>=0.104.0", "uvicorn[standard]>=0.24.0"],
    Platform.CUSTOM: [],
}

# Standard files every generated bot includes
BASE_FILES = [
    "README.md",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "main.py",
    "config.py",
    "bot/__init__.py",
    "bot/handler.py",
    "bot/logger_setup.py",
]

DOCKER_FILES = ["Dockerfile", "docker-compose.yml", ".dockerignore"]
CI_FILES = [".github/workflows/ci.yml"]
TEST_FILES = ["tests/__init__.py", "tests/test_handler.py"]


def build_plan(spec: BotSpec) -> ProjectPlan:
    """Generate a ProjectPlan from a BotSpec."""
    files = list(BASE_FILES)

    if spec.include_docker:
        files.extend(DOCKER_FILES)
    if spec.include_ci:
        files.extend(CI_FILES)
    if spec.include_tests:
        files.extend(TEST_FILES)

    platform_deps = list(PLATFORM_DEPS.get(spec.platform, []))
    all_deps = platform_deps + spec.dependencies

    notes = [
        f"Platform: {spec.platform.value}",
        f"Features: {', '.join(spec.features)}",
        f"Total files to generate: {len(files)}",
    ]

    logger.info("Plan built for '%s': %d files, %d deps", spec.name, len(files), len(all_deps))

    return ProjectPlan(
        spec=spec,
        files_to_generate=files,
        platform_deps=all_deps,
        context_notes=notes,
    )
