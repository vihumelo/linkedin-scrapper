"""Testes da seleção de adapter de cache pela configuração."""

from pathlib import Path

import pytest

from app.adapters.cache.sqlite import SQLiteJobCache
from app.core.config import Settings
from app.core.dependencies import create_job_cache


def test_creates_sqlite_adapter_with_configured_path(tmp_path: Path) -> None:
    """Seleciona SQLite e repassa o caminho configurado sem fixá-lo no adapter."""

    database_path = tmp_path / "custom" / "cache.db"
    settings = Settings(cache_backend="sqlite", cache_sqlite_path=database_path)

    cache = create_job_cache(settings)

    assert isinstance(cache, SQLiteJobCache)
    assert cache._database_path == database_path


def test_rejects_unknown_cache_backend() -> None:
    """Falha explicitamente quando a configuração seleciona um adapter inexistente."""

    settings = Settings(cache_backend="redis")

    with pytest.raises(ValueError, match="Backend de cache não suportado"):
        create_job_cache(settings)
