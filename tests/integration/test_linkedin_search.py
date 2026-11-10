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
    reason="teste online desativado; habilite-o explicitamente com RUN_LINKEDIN_INTEGRATION=1",
)
def test_linkedin_search_integration() -> None:
    """Queries real jobs and validates the essential integrated response contract."""

    settings = Settings()
    if not settings.linkedin_li_at or not settings.linkedin_jsessionid:
        pytest.skip("cookies do LinkedIn não estão configurados no ambiente")

    async def search() -> None:
        async with create_authenticated_http_client(settings) as http_client:
            response = await JobSearchService(
                AuthenticatedLinkedInClient(http_client, settings)
            ).search(
                keywords="biomedicina",
                geo_id="106057199",
                start=0,
            )

        job_ids = [job.id for job in response.jobs]
        assert response.query.keywords == "biomedicina"
        assert response.pagination.count == len(response.jobs)
        assert response.jobs, "A busca online não retornou vagas."
        assert len(job_ids) == len(set(job_ids)), "A resposta contém IDs de vaga duplicados."
        assert all(job.title or job.company or job.location for job in response.jobs)

    asyncio.run(search())
