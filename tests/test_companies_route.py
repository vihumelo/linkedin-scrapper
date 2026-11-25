"""Offline tests for the company search HTTP endpoint."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.clients.linkedin_session import (
    LinkedInAuthenticationError,
    LinkedInCredentialsError,
    LinkedInResponseError,
    LinkedInServiceUnavailableError,
    LinkedInTimeoutError,
)
from app.clients.linkedin_voyager_client import VoyagerNotFoundError
from app.core.dependencies import get_linkedin_voyager_client
from app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"


class FakeLinkedInVoyagerClient:
    """Fake client that returns a sanitized real Voyager response."""

    def __init__(self, fixture: str = "linkedin_company_search_voyager.json") -> None:
        """Selects the fixture returned for every search."""

        self.fixture = fixture
        self.calls: list[tuple[str, int]] = []

    async def search_companies(self, name: str, start: int) -> dict[str, object]:
        """Records the query and returns the fixture payload."""

        self.calls.append((name, start))
        return json.loads((FIXTURES / self.fixture).read_text(encoding="utf-8"))


def make_client(voyager_client: object) -> TestClient:
    """Creates a test client whose Voyager dependency is replaced."""

    app = create_app()
    app.dependency_overrides[get_linkedin_voyager_client] = lambda: voyager_client
    return TestClient(app)


def test_search_companies_returns_ids_for_job_search() -> None:
    """Returns the documented contract with companies in LinkedIn's order."""

    voyager_client = FakeLinkedInVoyagerClient()

    with make_client(voyager_client) as client:
        response = client.get("/api/companies/search", params={"name": "corporate"})

    assert response.status_code == 200
    assert voyager_client.calls == [("corporate", 0)]
    body = response.json()
    assert body["query"] == {"name": "corporate", "start": 0}
    assert body["pagination"] == {
        "start": 0,
        "count": 10,
        "total": 1000,
        "next_start": 10,
        "has_next": True,
    }
    assert body["companies"][0] == {
        "id": "10248363",
        "name": "Corporate Rebels",
        "industry_location": "Research Services • Eindhoven, North Brabant",
        "followers": "216K followers",
        "url": "https://www.linkedin.com/company/corporate-rebels---the-search-for-the-happy-grail/",
    }


def test_search_companies_returns_empty_list_without_matches() -> None:
    """Treats a search without matches as a successful empty result."""

    voyager_client = FakeLinkedInVoyagerClient("linkedin_company_search_voyager_empty.json")

    with make_client(voyager_client) as client:
        response = client.get("/api/companies/search", params={"name": "zqxjvkwpyhgf"})

    assert response.status_code == 200
    assert response.json()["companies"] == []
    assert response.json()["pagination"]["has_next"] is False


@pytest.mark.parametrize(
    "params",
    [{}, {"name": ""}, {"name": "   "}, {"name": "acme", "start": "-1"}],
)
def test_search_companies_rejects_invalid_parameters(params: dict[str, str]) -> None:
    """Rejects missing or blank names and negative offsets before calling LinkedIn."""

    voyager_client = FakeLinkedInVoyagerClient()

    with make_client(voyager_client) as client:
        response = client.get("/api/companies/search", params=params)

    assert response.status_code == 422
    assert voyager_client.calls == []


@pytest.mark.parametrize(
    ("upstream_error", "expected_status"),
    [
        (LinkedInCredentialsError("missing credentials"), 503),
        (LinkedInServiceUnavailableError("unavailable"), 503),
        (LinkedInTimeoutError("timed out"), 504),
        (LinkedInAuthenticationError("unauthorized"), 502),
        (VoyagerNotFoundError("not found"), 502),
        (LinkedInResponseError("invalid response"), 502),
    ],
)
def test_search_companies_maps_upstream_errors(
    upstream_error: Exception,
    expected_status: int,
) -> None:
    """Converts integration errors into the documented HTTP statuses."""

    class FailingClient:
        async def search_companies(self, name: str, start: int) -> dict[str, object]:
            raise upstream_error

    with make_client(FailingClient()) as client:
        response = client.get("/api/companies/search", params={"name": "acme"})

    assert response.status_code == expected_status
    assert "detail" in response.json()


def test_search_companies_reports_unrecognized_response_format() -> None:
    """Returns 502 when LinkedIn answers with a structure the parser does not recognize."""

    class UnexpectedPayloadClient:
        async def search_companies(self, name: str, start: int) -> dict[str, object]:
            return {"data": {"status": 200}}

    with make_client(UnexpectedPayloadClient()) as client:
        response = client.get("/api/companies/search", params={"name": "acme"})

    assert response.status_code == 502
    assert response.json() == {"detail": "The LinkedIn response format is not recognized."}
