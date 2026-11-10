"""Construction and access to shared application dependencies."""

from fastapi import Request

from app.adapters.cache.sqlite import SQLiteJobCache
from app.clients.authenticated_client import AuthenticatedLinkedInClient
from app.clients.public_client import PublicLinkedInClient
from app.core.config import Settings
from app.ports.job_cache import JobCache


def create_job_cache(settings: Settings) -> JobCache:
    """Selects and instantiates the configured cache adapter."""

    backend = settings.cache_backend.casefold().strip()
    if backend == "sqlite":
        return SQLiteJobCache(settings.cache_sqlite_path)
    raise ValueError(f"Backend de cache não suportado: {settings.cache_backend}.")


def get_job_cache(request: Request) -> JobCache:
    """Returns the shared cache created during the application lifecycle."""

    return request.app.state.job_cache


def get_authenticated_linkedin_client(request: Request) -> AuthenticatedLinkedInClient:
    """Returns the shared authenticated session created during the application lifecycle."""

    return request.app.state.authenticated_linkedin_client


def get_public_linkedin_client(request: Request) -> PublicLinkedInClient:
    """Returns the shared public session created during the application lifecycle."""

    return request.app.state.public_linkedin_client
