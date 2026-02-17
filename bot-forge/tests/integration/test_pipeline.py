"""Integration tests: run the full pipeline end-to-end."""

import tempfile
from pathlib import Path

import pytest

from core.database import JobRepository
from core.models import BotSpec, EnvVarSpec, PipelineStage, Platform
from core.pipeline import run_pipeline


def _get_templates_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "templates"


@pytest.mark.asyncio
async def test_full_pipeline_cli_bot():
    """Run the complete pipeline for a CLI echo bot."""
    spec = BotSpec(
        name="integration-cli-bot",
        platform=Platform.CLI,
        description="Integration test CLI bot",
        features=["echo"],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "test.db"
        output_dir = tmp / "output"
        output_dir.mkdir()

        repo = JobRepository(db_path)
        await repo.init()

        job = await run_pipeline(spec, repo, _get_templates_dir(), output_dir)

        assert job.stage == PipelineStage.DONE
        assert job.error is None
        assert job.output_path is not None

        project_dir = Path(job.output_path)
        assert project_dir.exists()
        assert (project_dir / "main.py").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / "requirements.txt").exists()

        # Check archive was created
        archive = output_dir / f"{spec.name}.tar.gz"
        assert archive.exists()


@pytest.mark.asyncio
async def test_full_pipeline_telegram_bot():
    """Run the complete pipeline for a Telegram echo bot."""
    spec = BotSpec(
        name="integration-tg-bot",
        platform=Platform.TELEGRAM,
        description="Integration test Telegram bot",
        features=["echo"],
        env_vars=[EnvVarSpec(name="TELEGRAM_BOT_TOKEN", description="Bot token")],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "test.db"
        output_dir = tmp / "output"
        output_dir.mkdir()

        repo = JobRepository(db_path)
        await repo.init()

        job = await run_pipeline(spec, repo, _get_templates_dir(), output_dir)

        assert job.stage == PipelineStage.DONE
        assert job.output_path is not None

        project_dir = Path(job.output_path)
        main_py = (project_dir / "main.py").read_text()
        assert "TELEGRAM_BOT_TOKEN" in main_py
        assert "echo" in (project_dir / "bot" / "handler.py").read_text().lower()


@pytest.mark.asyncio
async def test_full_pipeline_web_api_bot():
    """Run the complete pipeline for a Web API bot."""
    spec = BotSpec(
        name="integration-api-bot",
        platform=Platform.WEB_API,
        description="Integration test web API bot",
        features=["echo"],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "test.db"
        output_dir = tmp / "output"
        output_dir.mkdir()

        repo = JobRepository(db_path)
        await repo.init()

        job = await run_pipeline(spec, repo, _get_templates_dir(), output_dir)

        assert job.stage == PipelineStage.DONE
        assert job.output_path is not None


@pytest.mark.asyncio
async def test_job_persisted_in_db():
    """Verify the job record is persisted and retrievable."""
    spec = BotSpec(
        name="db-test-bot",
        platform=Platform.CLI,
        description="DB persistence test",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "test.db"
        output_dir = tmp / "output"
        output_dir.mkdir()

        repo = JobRepository(db_path)
        await repo.init()

        job = await run_pipeline(spec, repo, _get_templates_dir(), output_dir)

        retrieved = await repo.get(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.spec.name == "db-test-bot"
        assert retrieved.stage == PipelineStage.DONE

        all_jobs = await repo.list_all()
        assert len(all_jobs) >= 1
