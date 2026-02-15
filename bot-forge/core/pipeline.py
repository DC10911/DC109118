"""Pipeline orchestrator: runs the full Intake→Deploy factory flow."""

from __future__ import annotations

import logging
from pathlib import Path

from agents.generator import generate_project
from agents.packager import package_project
from agents.planner import build_plan
from agents.retriever import retrieve_context
from agents.reviewer import review_project
from agents.tester import run_tests
from core.database import JobRepository
from core.models import BotSpec, JobRecord, PipelineStage

logger = logging.getLogger("botforge.pipeline")


async def run_pipeline(
    spec: BotSpec,
    repo: JobRepository,
    templates_dir: Path,
    output_dir: Path,
) -> JobRecord:
    """Execute the full bot-generation pipeline and return the job record."""
    job = JobRecord(spec=spec)
    await repo.save(job)
    logger.info("[%s] Pipeline started for bot '%s'", job.id, spec.name)

    try:
        # 1. Intake — spec already validated via Pydantic
        job.advance(PipelineStage.INTAKE)
        await repo.save(job)
        logger.info("[%s] Stage: intake (validated)", job.id)

        # 2. Plan
        job.advance(PipelineStage.PLAN)
        await repo.save(job)
        plan = build_plan(spec)
        logger.info("[%s] Stage: plan (%d files planned)", job.id, len(plan.files_to_generate))

        # 3. Retrieve docs
        job.advance(PipelineStage.RETRIEVE_DOCS)
        await repo.save(job)
        plan = retrieve_context(plan)
        logger.info("[%s] Stage: retrieve_docs", job.id)

        # 4. Generate
        job.advance(PipelineStage.GENERATE)
        await repo.save(job)
        project_dir = generate_project(plan, templates_dir, output_dir)
        job.output_path = str(project_dir)
        logger.info("[%s] Stage: generate -> %s", job.id, project_dir)

        # 5. Test
        job.advance(PipelineStage.TEST)
        await repo.save(job)
        test_result = await run_tests(project_dir)
        job.test_result = test_result
        logger.info("[%s] Stage: test (passed=%s)", job.id, test_result.passed)

        # 6. Review
        job.advance(PipelineStage.REVIEW)
        await repo.save(job)
        review = review_project(project_dir)
        job.review_report = review
        logger.info("[%s] Stage: review (passed=%s)", job.id, review.passed)

        # 7. Package
        job.advance(PipelineStage.PACKAGE)
        await repo.save(job)
        archive = package_project(project_dir)
        logger.info("[%s] Stage: package -> %s", job.id, archive)

        # 8. Deploy (output to filesystem)
        job.advance(PipelineStage.DEPLOY)
        await repo.save(job)
        logger.info("[%s] Stage: deploy (complete)", job.id)

        # Done
        job.advance(PipelineStage.DONE)
        await repo.save(job)
        logger.info("[%s] Pipeline DONE for '%s'", job.id, spec.name)

    except Exception as exc:
        logger.exception("[%s] Pipeline FAILED at stage %s", job.id, job.stage.value)
        job.fail(str(exc))
        await repo.save(job)

    return job
