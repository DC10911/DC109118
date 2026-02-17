"""Docs retriever agent: fetches best-practice context for generation."""

from __future__ import annotations

import logging

from core.models import Platform, ProjectPlan

logger = logging.getLogger("botforge.retriever")

# Embedded best-practice snippets per platform (offline-friendly).
# In a production system this would query a docs index or external API.
PLATFORM_GUIDES: dict[Platform, str] = {
    Platform.TELEGRAM: (
        "Use python-telegram-bot v20+ with ApplicationBuilder pattern. "
        "Register handlers via add_handler(). Use ConversationHandler for multi-step flows. "
        "Store bot token in environment variable TELEGRAM_BOT_TOKEN."
    ),
    Platform.DISCORD: (
        "Use discord.py v2+ with commands.Bot or Client. "
        "Register event handlers with @bot.event or @bot.command(). "
        "Store bot token in DISCORD_BOT_TOKEN env var."
    ),
    Platform.SLACK: (
        "Use slack-bolt with App(token=...). Register listeners with @app.message() or @app.command(). "
        "Requires SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET."
    ),
    Platform.CLI: (
        "Use click for CLI argument parsing. Group commands with @click.group(). "
        "Support --verbose and --config flags."
    ),
    Platform.WEB_API: (
        "Use FastAPI with APIRouter. Add health endpoint at /health. "
        "Use Pydantic models for request/response validation."
    ),
    Platform.CUSTOM: "No platform-specific guidance. Implement a generic main.py entry point.",
}


def retrieve_context(plan: ProjectPlan) -> ProjectPlan:
    """Enrich the plan with platform-specific context notes."""
    guide = PLATFORM_GUIDES.get(plan.spec.platform, "")
    if guide:
        plan.context_notes.append(f"Platform guide: {guide}")
    logger.info("Context retrieved for platform=%s", plan.spec.platform.value)
    return plan
