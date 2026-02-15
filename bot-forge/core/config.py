"""BOT-FORGE configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path = field(default_factory=lambda: Path(os.getenv("BOTFORGE_DB_PATH", "./data/botforge.db")))
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("BOTFORGE_OUTPUT_DIR", "./output")))
    log_level: str = field(default_factory=lambda: os.getenv("BOTFORGE_LOG_LEVEL", "INFO"))
    host: str = field(default_factory=lambda: os.getenv("BOTFORGE_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("BOTFORGE_PORT", "8000")))
    templates_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "templates")

    def ensure_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
