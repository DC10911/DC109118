"""Generator agent: renders project files from Jinja2 templates."""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.models import ProjectPlan

logger = logging.getLogger("botforge.generator")


def _build_jinja_env(templates_dir: Path) -> Environment:
    loaders_dirs = []
    if templates_dir.exists():
        loaders_dirs.append(str(templates_dir))
    common = templates_dir / "common"
    if common.exists():
        loaders_dirs.append(str(common))
    if not loaders_dirs:
        raise FileNotFoundError(f"Templates directory not found: {templates_dir}")
    return Environment(
        loader=FileSystemLoader(loaders_dirs),
        autoescape=select_autoescape(disabled_extensions=("txt", "md", "py", "yml", "toml")),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def generate_project(plan: ProjectPlan, templates_dir: Path, output_dir: Path) -> Path:
    """Render all planned files into output_dir/<bot-name>/."""
    project_dir = output_dir / plan.spec.name
    project_dir.mkdir(parents=True, exist_ok=True)

    env = _build_jinja_env(templates_dir)

    # Template context available in every template
    ctx = {
        "spec": plan.spec,
        "plan": plan,
        "platform": plan.spec.platform.value,
        "bot_name": plan.spec.name,
        "description": plan.spec.description,
        "features": plan.spec.features,
        "env_vars": plan.spec.env_vars,
        "dependencies": plan.platform_deps + plan.spec.dependencies,
        "logging_level": plan.spec.logging_level.value,
        "include_docker": plan.spec.include_docker,
        "include_ci": plan.spec.include_ci,
        "include_tests": plan.spec.include_tests,
    }

    rendered_count = 0
    for rel_path in plan.files_to_generate:
        template_name = _resolve_template(env, plan.spec.platform.value, rel_path)
        if template_name is None:
            logger.warning("No template found for %s, skipping", rel_path)
            continue

        template = env.get_template(template_name)
        content = template.render(**ctx)

        out_file = project_dir / rel_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(content, encoding="utf-8")
        rendered_count += 1

    logger.info("Generated %d/%d files in %s", rendered_count, len(plan.files_to_generate), project_dir)
    return project_dir


def _resolve_template(env: Environment, platform: str, rel_path: str) -> str | None:
    """Try platform-specific template first, then common."""
    candidates = [
        f"{platform}/{rel_path}.j2",
        f"{rel_path}.j2",
    ]
    for candidate in candidates:
        try:
            env.get_template(candidate)
            return candidate
        except Exception:
            continue
    return None
