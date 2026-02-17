"""BOT-FORGE CLI interface."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.config import get_settings
from core.database import JobRepository
from core.logging_setup import setup_logging
from core.models import BotSpec, PipelineStage
from core.pipeline import run_pipeline

console = Console()


def _get_repo() -> JobRepository:
    settings = get_settings()
    settings.ensure_dirs()
    return JobRepository(settings.db_path)


def _run_async(coro):
    return asyncio.run(coro)


@click.group()
@click.option("--verbose", is_flag=True, help="Enable debug logging")
def main(verbose: bool) -> None:
    """BOT-FORGE: Meta-bot factory that generates production-ready bots."""
    level = "DEBUG" if verbose else get_settings().log_level
    setup_logging(level)


@main.command()
@click.argument("spec_file", type=click.Path(exists=True))
def forge(spec_file: str) -> None:
    """Generate a new bot from a JSON spec file.

    SPEC_FILE: Path to a JSON file containing the bot specification.
    """
    settings = get_settings()
    settings.ensure_dirs()

    with open(spec_file, encoding="utf-8") as f:
        raw = json.load(f)

    try:
        spec = BotSpec.model_validate(raw)
    except Exception as e:
        console.print(f"[red]Invalid spec:[/red] {e}")
        raise SystemExit(1)

    console.print(Panel(f"Forging bot: [bold cyan]{spec.name}[/bold cyan]\n"
                        f"Platform: {spec.platform.value}\n"
                        f"Features: {', '.join(spec.features)}",
                        title="BOT-FORGE", border_style="blue"))

    repo = _get_repo()

    async def _run():
        await repo.init()
        return await run_pipeline(spec, repo, settings.templates_dir, settings.output_dir)

    job = _run_async(_run())

    if job.stage == PipelineStage.DONE:
        console.print(f"\n[green]Bot '{spec.name}' generated successfully![/green]")
        console.print(f"Output: [bold]{job.output_path}[/bold]")
        console.print(f"Archive: [bold]{settings.output_dir / spec.name}.tar.gz[/bold]")

        if job.test_result:
            status = "[green]PASSED[/green]" if job.test_result.passed else "[red]FAILED[/red]"
            console.print(f"Tests: {status}")

        if job.review_report:
            status = "[green]PASSED[/green]" if job.review_report.passed else "[red]FAILED[/red]"
            console.print(f"Review: {status}")
            for w in job.review_report.warnings:
                console.print(f"  [yellow]Warning:[/yellow] {w}")
    else:
        console.print(f"\n[red]Pipeline failed at stage: {job.stage.value}[/red]")
        if job.error:
            console.print(f"Error: {job.error}")
        raise SystemExit(1)


@main.command()
def jobs() -> None:
    """List recent bot-generation jobs."""
    repo = _get_repo()

    async def _run():
        await repo.init()
        return await repo.list_all()

    records = _run_async(_run())

    if not records:
        console.print("[dim]No jobs found.[/dim]")
        return

    table = Table(title="BOT-FORGE Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Bot Name", style="bold")
    table.add_column("Platform")
    table.add_column("Stage", style="green")
    table.add_column("Created")

    for job in records:
        stage_style = "green" if job.stage == PipelineStage.DONE else "red" if job.stage == PipelineStage.FAILED else "yellow"
        table.add_row(
            job.id,
            job.spec.name,
            job.spec.platform.value,
            f"[{stage_style}]{job.stage.value}[/{stage_style}]",
            job.created_at[:19],
        )

    console.print(table)


@main.command()
@click.argument("job_id")
def status(job_id: str) -> None:
    """Show detailed status of a specific job."""
    repo = _get_repo()

    async def _run():
        await repo.init()
        return await repo.get(job_id)

    job = _run_async(_run())

    if job is None:
        console.print(f"[red]Job '{job_id}' not found.[/red]")
        raise SystemExit(1)

    console.print(Panel(
        f"Bot: [bold]{job.spec.name}[/bold]\n"
        f"Platform: {job.spec.platform.value}\n"
        f"Stage: {job.stage.value}\n"
        f"Created: {job.created_at}\n"
        f"Updated: {job.updated_at}\n"
        f"Output: {job.output_path or 'N/A'}\n"
        f"Error: {job.error or 'None'}",
        title=f"Job {job.id}",
        border_style="blue",
    ))

    if job.test_result:
        console.print(f"\nTest Results: {'PASSED' if job.test_result.passed else 'FAILED'}")
        console.print(f"  Files checked: {job.test_result.total}")
        console.print(f"  Failures: {job.test_result.failures}")

    if job.review_report:
        console.print(f"\nReview: {'PASSED' if job.review_report.passed else 'FAILED'}")
        for issue in job.review_report.issues:
            console.print(f"  [red]Issue:[/red] {issue}")
        for warn in job.review_report.warnings:
            console.print(f"  [yellow]Warning:[/yellow] {warn}")


@main.command()
def platforms() -> None:
    """List supported bot platforms."""
    table = Table(title="Supported Platforms")
    table.add_column("Platform", style="cyan")
    table.add_column("Description")

    platforms_info = [
        ("telegram", "Telegram bots using python-telegram-bot"),
        ("discord", "Discord bots using discord.py"),
        ("slack", "Slack bots using slack-bolt"),
        ("cli", "Command-line interface bots using click"),
        ("web-api", "REST API bots using FastAPI"),
        ("custom", "Generic bot with minimal scaffolding"),
    ]
    for name, desc in platforms_info:
        table.add_row(name, desc)

    console.print(table)


if __name__ == "__main__":
    main()
