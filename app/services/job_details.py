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
                    "Failed to read the cache; querying LinkedIn.",
                    exc_info=True,
                    extra={"event": "cache.lookup", "result": "error"},
                )
            else:
                if cached_job is None:
                    logger.info(
                        "The job details cache returned no match.",
                        extra={"event": "cache.lookup", "result": "miss"},
                    )
                elif _is_cacheable(cached_job) and cached_job.id == job_id:
                    logger.info(
                        "Job details returned from the cache.",
                        extra={"event": "cache.lookup", "result": "hit"},
                    )
                    return JobDetailResponse(is_cached=True, job=cached_job)
                else:
                    logger.warning(
                        "The cache contains incomplete or inconsistent job details.",
                        extra={"event": "cache.lookup", "result": "invalid"},
                    )
        else:
            logger.info(
                "Cache read skipped because an explicit refresh was requested.",
                extra={"event": "cache.lookup", "result": "bypassed", "reason": "refresh"},
            )

        payload = await self._linkedin_client.get_job_details(job_id)
        job = parse_job_detail_voyager(payload, job_id)
        if _is_cacheable(job):
            try:
                await self._cache.save(job)
                logger.info(
                    "Job details saved to the cache.",
                    extra={"event": "cache.write", "result": "saved"},
                )
            except JobCacheError:
                logger.warning(
                    "Failed to save job details to the cache.",
                    exc_info=True,
                    extra={"event": "cache.write", "result": "error"},
                )
        else:
            logger.info(
                "Job details are incomplete; the cache was not updated.",
                extra={"event": "cache.write", "result": "skipped", "reason": "incomplete"},
            )
        return JobDetailResponse(is_cached=False, job=job)


def _is_cacheable(job: JobDetail) -> bool:
    """Checks whether the required fields are populated before persisting a job."""

    required_fields = ("id", "title", "company", "url", "description_text")
    for field in required_fields:
        value = getattr(job, field, None)
        if not isinstance(value, str) or not value.strip():
            return False
    return True
