"""Unit tests for the retriever agent."""

from agents.planner import build_plan
from agents.retriever import retrieve_context
from core.models import BotSpec, Platform


def test_retrieve_adds_context():
    spec = BotSpec(name="ctx-bot", platform=Platform.TELEGRAM, description="Test context")
    plan = build_plan(spec)
    initial_notes = len(plan.context_notes)
    enriched = retrieve_context(plan)
    assert len(enriched.context_notes) > initial_notes


def test_retrieve_all_platforms():
    for platform in Platform:
        spec = BotSpec(name=f"ctx-{platform.value}", platform=platform, description="Test")
        plan = build_plan(spec)
        enriched = retrieve_context(plan)
        assert any("guide" in n.lower() or "Platform" in n for n in enriched.context_notes)
