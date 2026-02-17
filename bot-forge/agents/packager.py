"""Packager agent: bundles the generated project into a tar.gz archive."""

from __future__ import annotations

import logging
import shutil
import tarfile
from pathlib import Path

logger = logging.getLogger("botforge.packager")


def package_project(project_dir: Path) -> Path:
    """Create a tar.gz archive of the project directory."""
    archive_path = project_dir.parent / f"{project_dir.name}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(project_dir, arcname=project_dir.name)

    size_kb = archive_path.stat().st_size / 1024
    logger.info("Packaged %s -> %s (%.1f KB)", project_dir.name, archive_path.name, size_kb)
    return archive_path
