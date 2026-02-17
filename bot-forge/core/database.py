"""SQLite repository for BOT-FORGE job records (async, swappable)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import aiosqlite

from core.models import JobRecord

logger = logging.getLogger("botforge.db")

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class JobRepository:
    """Async repository wrapping SQLite. Replace with Postgres by swapping this class."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(CREATE_TABLE)
            await db.commit()
        logger.info("Database initialized at %s", self._db_path)

    async def save(self, job: JobRecord) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO jobs (id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (job.id, job.model_dump_json(), job.created_at, job.updated_at),
            )
            await db.commit()

    async def get(self, job_id: str) -> JobRecord | None:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("SELECT data FROM jobs WHERE id = ?", (job_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return JobRecord.model_validate_json(row[0])

    async def list_all(self, limit: int = 50) -> list[JobRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT data FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
            return [JobRecord.model_validate_json(r[0]) for r in rows]

    async def delete(self, job_id: str) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            await db.commit()
            return cursor.rowcount > 0
