"""Unit tests for the planner agent."""

from agents.planner import build_plan
from core.models import BotSpec, Platform


def test_build_plan_telegram():
    spec = BotSpec(name="tg-bot", platform=Platform.TELEGRAM, description="Test TG bot")
    plan = build_plan(spec)
    assert plan.spec.name == "tg-bot"
    assert "python-telegram-bot>=20.7" in plan.platform_deps
    assert "main.py" in plan.files_to_generate
    assert "README.md" in plan.files_to_generate
    assert "Dockerfile" in plan.files_to_generate


def test_build_plan_no_docker():
    spec = BotSpec(
        name="no-docker-bot",
        platform=Platform.CLI,
        description="Bot without docker",
        include_docker=False,
    )
    plan = build_plan(spec)
    assert "Dockerfile" not in plan.files_to_generate
    assert "docker-compose.yml" not in plan.files_to_generate


def test_build_plan_no_tests():
    spec = BotSpec(
        name="no-test-bot",
        platform=Platform.CLI,
        description="Bot without tests",
        include_tests=False,
    )
    plan = build_plan(spec)
    assert "tests/test_handler.py" not in plan.files_to_generate


def test_build_plan_no_ci():
    spec = BotSpec(
        name="no-ci-bot",
        platform=Platform.CLI,
        description="Bot without CI",
        include_ci=False,
    )
    plan = build_plan(spec)
    assert ".github/workflows/ci.yml" not in plan.files_to_generate


def test_build_plan_all_platforms():
    for platform in Platform:
        spec = BotSpec(name=f"test-{platform.value}", platform=platform, description="Test")
        plan = build_plan(spec)
        assert len(plan.files_to_generate) > 0
        assert len(plan.context_notes) > 0
