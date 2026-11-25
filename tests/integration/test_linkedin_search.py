"""Optional online test for the real LinkedIn integration.

Run it explicitly with:
    RUN_LINKEDIN_INTEGRATION=1 .venv/bin/python -m pytest tests/integration/test_linkedin_search.py
"""

import asyncio
import os

import pytest

from app.clients.authenticated_client import (
    AuthenticatedLinkedInClient,
    create_authenticated_http_client,
)
from app.core.config import Settings
from app.services.job_search import JobSearchService


@pytest.mark.skipif(
    os.getenv("RUN_LINKEDIN_INTEGRATION") != "1",
    reason="Online test disabled; enable it explicitly with RUN_LINKEDIN_INTEGRATION=1",
)
def test_linkedin_search_integration() -> None:
    """Queries real jobs and validates the essential integrated response contract."""

    settings = Settings()
    if not settings.linkedin_li_at or not settings.linkedin_jsessionid:
        pytest.skip("LinkedIn authentication cookies are not configured in the environment")

    async def search() -> None:
        async with create_authenticated_http_client(settings) as http_client:
            response = await JobSearchService(
                AuthenticatedLinkedInClient(http_client, settings)
            ).search(
                keywords="software engineer",
                geo_id="90009574",
                f_tpr="r2592000",
                start=0,
            )

        job_ids = [job.id for job in response.jobs]
        assert response.query.keywords == "software engineer"
        assert response.query.company_id is None
        assert response.query.geo_id == "90009574"
        assert response.query.f_tpr == "r2592000"
        assert response.pagination.count == len(response.jobs)
        assert response.jobs, "The online search returned no jobs."
        assert len(job_ids) == len(set(job_ids)), "The response contains duplicate job IDs."
        assert all(job.title or job.company or job.location for job in response.jobs)

    asyncio.run(search())


@pytest.mark.skipif(
    os.getenv("RUN_LINKEDIN_INTEGRATION") != "1",
    reason="Online test disabled; enable it explicitly with RUN_LINKEDIN_INTEGRATION=1",
)
def test_linkedin_company_search_integration() -> None:
    """Queries Pfizer jobs by company ID without sending a user keyword."""

    settings = Settings()
    if not settings.linkedin_li_at or not settings.linkedin_jsessionid:
        pytest.skip("LinkedIn authentication cookies are not configured in the environment")

    async def search() -> None:
        async with create_authenticated_http_client(settings) as http_client:
            response = await JobSearchService(
                AuthenticatedLinkedInClient(http_client, settings)
            ).search(
                keywords=None,
                geo_id="90009574",
                f_tpr="r2592000",
                start=0,
                company_id="1185",
            )

        job_ids = [job.id for job in response.jobs]
        assert response.query.keywords is None
        assert response.query.company_id == "1185"
        assert response.pagination.count == len(response.jobs)
        assert response.jobs, "The company search returned no jobs."
        assert len(job_ids) == len(set(job_ids)), "The search contains duplicate job IDs."
        assert all(job.company and "pfizer" in job.company.casefold() for job in response.jobs)

    asyncio.run(search())
