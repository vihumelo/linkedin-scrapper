"""Orchestrates caching, public requests, and job detail extraction."""

import logging

from app.clients.authenticated_client import AuthenticatedLinkedInClient
from app.parsers.linkedin_voyager_job_details import parse_job_detail_voyager
from app.ports.job_cache import JobCache, JobCacheError
from app.schemas.jobs import JobDetail, JobDetailResponse

logger = logging.getLogger(__name__)


class JobDetailService:
    """Coordinates the authenticated request, parsing, and response construction."""

    def __init__(self, linkedin_client: AuthenticatedLinkedInClient, cache: JobCache) -> None:
        """Stores the injected authenticated client and cache port."""

        self._linkedin_client = linkedin_client
        self._cache = cache

    async def get_job(self, job_id: str, refresh: bool = False) -> JobDetailResponse:
        """Reads from the cache or LinkedIn and stores complete details when possible."""

        if not refresh:
            try:
                cached_job = await self._cache.get(job_id)
            except JobCacheError:
                logger.warning(
                    "Falha ao ler cache; consultando o LinkedIn.",
                    exc_info=True,
                    extra={"event": "cache.lookup", "result": "error"},
                )
            else:
                if cached_job is None:
                    logger.info(
                        "Cache de detalhes não encontrou a vaga.",
                        extra={"event": "cache.lookup", "result": "miss"},
                    )
                elif _is_cacheable(cached_job) and cached_job.id == job_id:
                    logger.info(
                        "Detalhes retornados do cache.",
                        extra={"event": "cache.lookup", "result": "hit"},
                    )
                    return JobDetailResponse(job=cached_job)
                else:
                    logger.warning(
                        "Cache contém detalhes incompletos ou inconsistentes.",
                        extra={"event": "cache.lookup", "result": "invalid"},
                    )
        else:
            logger.info(
                "Leitura do cache ignorada por atualização explícita.",
                extra={"event": "cache.lookup", "result": "bypassed", "reason": "refresh"},
            )

        payload = await self._linkedin_client.get_job_details(job_id)
        job = parse_job_detail_voyager(payload, job_id)
        if _is_cacheable(job):
            try:
                await self._cache.save(job)
                logger.info(
                    "Detalhes da vaga gravados no cache.",
                    extra={"event": "cache.write", "result": "saved"},
                )
            except JobCacheError:
                logger.warning(
                    "Falha ao gravar detalhes no cache.",
                    exc_info=True,
                    extra={"event": "cache.write", "result": "error"},
                )
        else:
            logger.info(
                "Detalhes insuficientes; cache não foi atualizado.",
                extra={"event": "cache.write", "result": "skipped", "reason": "incomplete"},
            )
        return JobDetailResponse(job=job)


def _is_cacheable(job: JobDetail) -> bool:
    """Checks whether the required fields are populated before persisting a job."""

    required_fields = ("id", "title", "company", "url", "description_text")
    for field in required_fields:
        value = getattr(job, field, None)
        if not isinstance(value, str) or not value.strip():
            return False
    return True
