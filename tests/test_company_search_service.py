"""Tests for the company search service response and pagination."""

import asyncio

import pytest

from app.core.json_types import JSONValue
from app.schemas.companies import CompanySearchResponse
from app.services.company_search import CompanySearchService

COMPANY_URN = "urn:li:fsd_entityResultViewModel:(urn:li:fsd_company:42,SEARCH_SRP,DEFAULT)"


class FakeVoyagerClient:
    """Fake Voyager client that returns a fixed company search payload."""

    def __init__(self, paging: JSONValue) -> None:
        """Stores the paging metadata returned with one company."""

        self.paging = paging
        self.calls: list[tuple[str, int]] = []

    async def search_companies(self, name: str, start: int) -> dict[str, JSONValue]:
        """Records the query and returns one company result."""

        self.calls.append((name, start))
        collection: dict[str, JSONValue] = {
            "elements": [{"items": [{"item": {"*entityResult": COMPANY_URN}}]}],
        }
        if self.paging is not None:
            collection["paging"] = self.paging
        return {
            "data": {"data": {"searchDashClustersByAll": collection}},
            "included": [
                {
                    "$type": "com.linkedin.voyager.dash.search.EntityResultViewModel",
                    "entityUrn": COMPANY_URN,
                    "title": {"text": "Acme"},
                }
            ],
        }


def search(client: FakeVoyagerClient, start: int) -> CompanySearchResponse:
    """Runs the service with the fake client."""

    service = CompanySearchService(client)
    return asyncio.run(service.search("acme", start))


@pytest.mark.parametrize(
    ("start", "total", "expected_has_next", "expected_next_start"),
    [
        (0, 25, True, 10),
        (10, 25, True, 20),
        (20, 25, False, None),
        (0, 10, False, None),
    ],
)
def test_search_builds_pagination_from_linkedin_paging(
    start: int,
    total: int,
    expected_has_next: bool,
    expected_next_start: int | None,
) -> None:
    """Uses LinkedIn's total and page size to decide whether another page exists."""

    client = FakeVoyagerClient({"count": 10, "start": start, "total": total})

    response = search(client, start)

    assert client.calls == [("acme", start)]
    assert response.query.model_dump() == {"name": "acme", "start": start}
    assert response.pagination.model_dump() == {
        "start": start,
        "count": 1,
        "total": total,
        "next_start": expected_next_start,
        "has_next": expected_has_next,
    }
    assert [company.id for company in response.companies] == ["42"]


@pytest.mark.parametrize("paging", [None, {"count": 0, "total": 5}])
def test_search_leaves_next_page_unknown_without_usable_paging(paging: JSONValue) -> None:
    """Does not guess the next page when the total or page size is unavailable."""

    response = search(FakeVoyagerClient(paging), 0)

    assert response.pagination.has_next is None
    assert response.pagination.next_start is None
