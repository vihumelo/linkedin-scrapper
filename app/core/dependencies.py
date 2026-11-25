"""Construction and access to shared application dependencies."""

from fastapi import Request

from app.adapters.cache.sqlite import SQLiteJobCache
from app.clients.linkedin_html_client import LinkedInHtmlClient
from app.clients.linkedin_voyager_client import LinkedInVoyagerClient
from app.core.config import Settings
from app.ports.job_cache import JobCache


def create_job_cache(settings: Settings) -> JobCache:
    """Selects and instantiates the configured cache adapter."""

    backend = settings.cache_backend.casefold().strip()
    if backend == "sqlite":
        return SQLiteJobCache(settings.cache_sqlite_path)
    raise ValueError(f"Unsupported cache backend: {settings.cache_backend}.")


def get_job_cache(request: Request) -> JobCache:
    """Returns the shared cache created during the application lifecycle."""

    return request.app.state.job_cache


def get_linkedin_html_client(request: Request) -> LinkedInHtmlClient:
    """Returns the shared HTML client created during the application lifecycle."""

    return request.app.state.linkedin_html_client


def get_linkedin_voyager_client(request: Request) -> LinkedInVoyagerClient:
    """Returns the shared Voyager client created during the application lifecycle."""

    return request.app.state.linkedin_voyager_client
