"""Orchestrates LinkedIn company searches and result extraction."""

import logging

from app.clients.linkedin_voyager_client import COMPANY_SEARCH_INTEGRATION, LinkedInVoyagerClient
from app.parsers.linkedin_voyager_companies import (
    CompanySearchStructureError,
    parse_company_search_voyager,
)
from app.schemas.companies import CompanyPagination, CompanyQuery, CompanySearchResponse

logger = logging.getLogger(__name__)


class CompanySearchService:
    """Coordinates the Voyager search, parsing, and response construction."""

    def __init__(self, voyager_client: LinkedInVoyagerClient) -> None:
        """Stores the client used to query LinkedIn's Voyager API."""

        self._voyager_client = voyager_client

    async def search(self, name: str, start: int) -> CompanySearchResponse:
        """Searches companies by name and builds the validated API response."""

        payload = await self._voyager_client.search_companies(name, start)
        try:
            page = parse_company_search_voyager(payload)
        except CompanySearchStructureError:
            logger.warning(
                "The LinkedIn company search response was not recognized.",
                extra={
                    "event": "upstream.response.unrecognized",
                    "integration": COMPANY_SEARCH_INTEGRATION,
                },
            )
            raise

        has_next: bool | None = None
        next_start: int | None = None
        if page.total is not None and page.page_size is not None and page.page_size > 0:
            has_next = start + page.page_size < page.total
            next_start = start + page.page_size if has_next else None

        return CompanySearchResponse(
            query=CompanyQuery(name=name, start=start),
            pagination=CompanyPagination(
                start=start,
                count=len(page.companies),
                total=page.total,
                next_start=next_start,
                has_next=has_next,
            ),
            companies=page.companies,
        )
