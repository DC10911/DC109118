"""Unit tests for BOT-FORGE models."""

import pytest
from pydantic import ValidationError

from core.models import BotSpec, EnvVarSpec, JobRecord, Platform, PipelineStage


class TestBotSpec:
    def test_valid_spec(self):
        spec = BotSpec(
            name="my-test-bot",
            platform=Platform.TELEGRAM,
            description="A test bot",
        )
        assert spec.name == "my-test-bot"
        assert spec.platform == Platform.TELEGRAM
        assert spec.features == ["echo"]

    def test_name_slug_normalization(self):
        spec = BotSpec(
            name="My Cool Bot",
            platform=Platform.CLI,
            description="Test bot",
        )
        assert spec.name == "my-cool-bot"

    def test_invalid_name_too_short(self):
        with pytest.raises(ValidationError):
            BotSpec(name="a", platform=Platform.CLI, description="Test")

    def test_invalid_description_too_short(self):
        with pytest.raises(ValidationError):
            BotSpec(name="test-bot", platform=Platform.CLI, description="ab")

    def test_env_vars(self):
        spec = BotSpec(
            name="env-bot",
            platform=Platform.TELEGRAM,
            description="Test with env vars",
            env_vars=[
                EnvVarSpec(name="TOKEN", description="Bot token"),
            ],
        )
        assert len(spec.env_vars) == 1
        assert spec.env_vars[0].name == "TOKEN"

    def test_all_platforms(self):
        for platform in Platform:
            spec = BotSpec(
                name=f"test-{platform.value}-bot",
                platform=platform,
                description="Testing all platforms",
            )
            assert spec.platform == platform


class TestJobRecord:
    def test_create_job(self):
        spec = BotSpec(name="job-test", platform=Platform.CLI, description="Test job")
        job = JobRecord(spec=spec)
        assert job.stage == PipelineStage.INTAKE
        assert job.error is None
        assert len(job.id) == 12

    def test_advance_stage(self):
        spec = BotSpec(name="job-test", platform=Platform.CLI, description="Test job")
        job = JobRecord(spec=spec)
        job.advance(PipelineStage.PLAN)
        assert job.stage == PipelineStage.PLAN

    def test_fail(self):
        spec = BotSpec(name="job-test", platform=Platform.CLI, description="Test job")
        job = JobRecord(spec=spec)
        job.fail("Something went wrong")
        assert job.stage == PipelineStage.FAILED
        assert job.error == "Something went wrong"
