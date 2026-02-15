"""Unit tests for the generator agent."""

import tempfile
from pathlib import Path

from agents.generator import generate_project
from agents.planner import build_plan
from agents.retriever import retrieve_context
from core.models import BotSpec, EnvVarSpec, Platform


def _get_templates_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "templates"


def test_generate_cli_bot():
    spec = BotSpec(
        name="test-cli-gen",
        platform=Platform.CLI,
        description="Generated CLI bot for testing",
        features=["echo"],
    )
    plan = build_plan(spec)
    plan = retrieve_context(plan)

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir)
        project_dir = generate_project(plan, _get_templates_dir(), output)

        assert project_dir.exists()
        assert (project_dir / "main.py").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / "requirements.txt").exists()
        assert (project_dir / "bot" / "handler.py").exists()

        # Check content was rendered (not raw Jinja)
        readme = (project_dir / "README.md").read_text()
        assert "test-cli-gen" in readme
        assert "{{" not in readme


def test_generate_telegram_bot():
    spec = BotSpec(
        name="test-tg-gen",
        platform=Platform.TELEGRAM,
        description="Generated Telegram bot for testing",
        features=["echo"],
        env_vars=[EnvVarSpec(name="TELEGRAM_BOT_TOKEN", description="Token")],
    )
    plan = build_plan(spec)
    plan = retrieve_context(plan)

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir)
        project_dir = generate_project(plan, _get_templates_dir(), output)

        assert (project_dir / "main.py").exists()
        main_content = (project_dir / "main.py").read_text()
        assert "TELEGRAM_BOT_TOKEN" in main_content
        assert "{{" not in main_content


def test_generate_includes_docker():
    spec = BotSpec(
        name="docker-bot",
        platform=Platform.CLI,
        description="Bot with docker",
        include_docker=True,
    )
    plan = build_plan(spec)
    plan = retrieve_context(plan)

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir)
        project_dir = generate_project(plan, _get_templates_dir(), output)
        assert (project_dir / "Dockerfile").exists()
        assert (project_dir / "docker-compose.yml").exists()
