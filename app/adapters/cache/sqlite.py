"""SQLite adapter for persisting job details."""

import asyncio
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from app.ports.job_cache import JobCache, JobCacheError
from app.schemas.jobs import JobDetail


class SQLiteJobCache(JobCache):
    """Stores complete job models in a local SQLite database."""

    def __init__(self, database_path: str | Path) -> None:
        """Sets the database path without performing blocking disk operations."""

        self._database_path = Path(database_path).expanduser()
        self._schema_ready = False
        self._schema_lock = threading.Lock()
        if str(database_path) == ":memory:":
            raise ValueError("O cache SQLite requer um arquivo para persistir entre conexões.")

    async def get(self, job_id: str) -> JobDetail | None:
        """Retrieves a job by ID, returning None when it does not exist."""

        try:
            return await asyncio.to_thread(self._get_sync, job_id)
        except (OSError, sqlite3.Error, ValidationError, ValueError) as exc:
            raise JobCacheError("Não foi possível ler o cache SQLite de vagas.") from exc

    async def save(self, job: JobDetail) -> None:
        """Inserts or updates a job and keeps timestamps in UTC."""

        try:
            await asyncio.to_thread(self._save_sync, job)
        except (OSError, sqlite3.Error, ValidationError, ValueError) as exc:
            raise JobCacheError("Não foi possível gravar no cache SQLite de vagas.") from exc

    async def delete(self, job_id: str) -> None:
        """Removes a job by ID without error when it is not stored."""

        try:
            await asyncio.to_thread(self._delete_sync, job_id)
        except (OSError, sqlite3.Error) as exc:
            raise JobCacheError("Não foi possível remover do cache SQLite de vagas.") from exc

    def _get_sync(self, job_id: str) -> JobDetail | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT job_json FROM job_cache WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        job = JobDetail.model_validate_json(row[0])
        if job.id != job_id:
            raise ValueError("O ID persistido não corresponde à chave do cache.")
        return job

    def _save_sync(self, job: JobDetail) -> None:
        now = datetime.now(UTC).isoformat(timespec="microseconds")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO job_cache (job_id, job_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    job_json = excluded.job_json,
                    updated_at = excluded.updated_at
                """,
                (job.id, job.model_dump_json(), now, now),
            )

    def _delete_sync(self, job_id: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM job_cache WHERE job_id = ?", (job_id,))

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Opens a transaction and creates the database, directories, and table as needed."""

        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self._database_path, timeout=10)) as connection:
            connection.execute("PRAGMA busy_timeout = 10000")
            self._ensure_schema(connection)
            with connection:
                yield connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        """Creates the table once per adapter, with protection for concurrent calls."""

        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_cache (
                    job_id TEXT PRIMARY KEY,
                    job_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
            self._schema_ready = True
