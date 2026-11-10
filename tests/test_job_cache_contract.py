"""Testes reutilizáveis do contrato de cache de detalhes de vagas."""

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.cache.sqlite import SQLiteJobCache
from app.ports.job_cache import JobCache
from app.schemas.jobs import JobDetail


def make_job(job_id: str, title: str = "Técnico de laboratório") -> JobDetail:
    """Monta detalhes válidos para o contrato de cache."""

    return JobDetail(
        id=job_id,
        title=title,
        company="Empresa Exemplo",
        location="São Paulo, Brasil",
        url=f"https://www.linkedin.com/jobs/view/{job_id}/",
        description_text="Descrição completa da vaga.",
        description_html="<p>Descrição completa da vaga.</p>",
    )


async def assert_job_cache_contract(cache: JobCache) -> None:
    """Valida ausência, leitura, upsert e remoção para qualquer adapter de cache."""

    job_id = "contract-job-1"
    assert await cache.get(job_id) is None

    original = make_job(job_id)
    await cache.save(original)
    assert await cache.get(job_id) == original

    updated = make_job(job_id, title="Analista de laboratório")
    await cache.save(updated)
    assert await cache.get(job_id) == updated

    await cache.delete(job_id)
    assert await cache.get(job_id) is None


def test_sqlite_adapter_obeys_reusable_job_cache_contract(tmp_path: Path) -> None:
    """Executa o contrato compartilhado contra o adapter SQLite."""

    cache = SQLiteJobCache(tmp_path / "nested" / "jobs.db")
    asyncio.run(assert_job_cache_contract(cache))


def test_sqlite_cache_persists_across_adapter_instances(tmp_path: Path) -> None:
    """Mantém dados gravados disponíveis após criar uma nova instância do adapter."""

    database_path = tmp_path / "jobs.db"
    job = make_job("persistent-job-2")

    async def save_and_reload() -> JobDetail | None:
        await SQLiteJobCache(database_path).save(job)
        return await SQLiteJobCache(database_path).get(job.id)

    assert asyncio.run(save_and_reload()) == job


def test_sqlite_timestamps_are_utc_and_upsert_preserves_creation_time(tmp_path: Path) -> None:
    """Grava timestamps UTC e altera updated_at sem substituir created_at."""

    database_path = tmp_path / "jobs.db"
    cache = SQLiteJobCache(database_path)
    job = make_job("timestamp-job-3")

    async def save_twice() -> None:
        await cache.save(job)
        await asyncio.sleep(0.002)
        await cache.save(job.model_copy(update={"title": "Título atualizado"}))

    asyncio.run(save_twice())
    with sqlite3.connect(database_path) as connection:
        created_at, updated_at = connection.execute(
            "SELECT created_at, updated_at FROM job_cache WHERE job_id = ?",
            (job.id,),
        ).fetchone()

    created = datetime.fromisoformat(created_at)
    updated = datetime.fromisoformat(updated_at)
    assert created.tzinfo == UTC
    assert updated.tzinfo == UTC
    assert updated > created


def test_sqlite_cache_handles_concurrent_writes(tmp_path: Path) -> None:
    """Preserva gravações concorrentes sem corromper os registros."""

    cache = SQLiteJobCache(tmp_path / "jobs.db")
    jobs = [make_job(f"concurrent-job-{index}") for index in range(12)]

    async def save_all() -> None:
        await asyncio.gather(*(cache.save(job) for job in jobs))
        stored = await asyncio.gather(*(cache.get(job.id) for job in jobs))
        assert stored == jobs

    asyncio.run(save_all())
