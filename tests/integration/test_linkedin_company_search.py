"""Optional online test for the real LinkedIn company search.

Run it explicitly with:
    pytest --integration --no-cov tests/integration/test_linkedin_company_search.py
"""

import asyncio

import pytest

from app.clients.linkedin_session import LinkedInSession, create_authenticated_http_client
from app.clients.linkedin_voyager_client import LinkedInVoyagerClient
from app.core.config import Settings
from app.services.company_search import CompanySearchService

pytestmark = pytest.mark.integration


def test_linkedin_company_search_by_name_integration(linkedin_settings: Settings) -> None:
    """Queries real companies by a multi-word name and validates the essential contract."""

    async def search() -> None:
        async with create_authenticated_http_client(linkedin_settings) as http_client:
            client = LinkedInVoyagerClient(
                LinkedInSession(http_client, linkedin_settings),
                linkedin_settings.linkedin_company_search_query_id,
            )
            response = await CompanySearchService(client).search("banco do brasil", 0)

        company_ids = [company.id for company in response.companies]
        assert response.companies, "The online company search returned no companies."
        assert all(company_id.isdigit() for company_id in company_ids)
        assert len(company_ids) == len(set(company_ids)), "The response has duplicate IDs."
        assert response.pagination.count == len(response.companies)

    asyncio.run(search())
