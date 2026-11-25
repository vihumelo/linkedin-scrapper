"""Orchestrates LinkedIn requests and result extraction."""

import logging
from typing import Literal

from app.clients.linkedin_html_client import JOBS_SEARCH_INTEGRATION, LinkedInHtmlClient
from app.parsers.linkedin_jobs import HTMLStructureError, parse_job_search_html
from app.schemas.jobs import (
    JobPagination,
    JobQuery,
    JobSearchResponse,
)

logger = logging.getLogger(__name__)


class JobSearchService:
    """Coordinates the external search, parsing, and response construction."""

    def __init__(self, linkedin_client: LinkedInHtmlClient) -> None:
        """Stores the client used to query LinkedIn."""

        self._linkedin_client = linkedin_client

    async def search(
        self,
        keywords: str | None,
        geo_id: str,
        f_tpr: Literal["r86400", "r604800", "r2592000"],
        start: int,
        company_id: str | None = None,
    ) -> JobSearchResponse:
        """Searches for jobs and builds the validated API response."""

        if company_id is None:
            html = await self._linkedin_client.search_jobs(keywords, geo_id, f_tpr, start)
        else:
            html = await self._linkedin_client.search_jobs(
                keywords,
                geo_id,
                f_tpr,
                start,
                company_id=company_id,
            )
        try:
            jobs, has_next = parse_job_search_html(html, start)
        except HTMLStructureError as exc:
            logger.warning(
                "The LinkedIn search results page was not recognized.",
                extra={
                    "event": "upstream.response.unrecognized",
                    "integration": JOBS_SEARCH_INTEGRATION,
                    "reason": exc.reason,
                    "html_bytes": len(html.encode()),
                },
            )
            raise
        count = len(jobs)
        next_start = start + count if has_next is True else None
        return JobSearchResponse(
            query=JobQuery(
                keywords=keywords,
                company_id=company_id,
                geo_id=geo_id,
                f_tpr=f_tpr,
            ),
            pagination=JobPagination(
                start=start,
                count=count,
                next_start=next_start,
                has_next=has_next,
            ),
            jobs=jobs,
        )
