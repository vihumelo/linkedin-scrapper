"""Construção e acesso às dependências compartilhadas da aplicação."""

from fastapi import Request

from app.adapters.cache.sqlite import SQLiteJobCache
from app.clients.authenticated_client import AuthenticatedLinkedInClient
from app.clients.public_client import PublicLinkedInClient
from app.core.config import Settings
from app.ports.job_cache import JobCache


def create_job_cache(settings: Settings) -> JobCache:
    """Seleciona e instancia o adapter de cache configurado."""

    backend = settings.cache_backend.casefold().strip()
    if backend == "sqlite":
        return SQLiteJobCache(settings.cache_sqlite_path)
    raise ValueError(f"Backend de cache não suportado: {settings.cache_backend}.")


def get_job_cache(request: Request) -> JobCache:
    """Obtém o cache compartilhado criado durante o ciclo de vida da aplicação."""

    return request.app.state.job_cache


def get_authenticated_linkedin_client(request: Request) -> AuthenticatedLinkedInClient:
    """Obtém a sessão autenticada compartilhada criada no ciclo de vida da aplicação."""

    return request.app.state.authenticated_linkedin_client


def get_public_linkedin_client(request: Request) -> PublicLinkedInClient:
    """Obtém a sessão pública compartilhada criada no ciclo de vida da aplicação."""

    return request.app.state.public_linkedin_client
