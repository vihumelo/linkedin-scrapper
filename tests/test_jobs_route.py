"""Tests for the job search HTTP endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.clients.authenticated_client import (
    LinkedInAuthenticationError,
    LinkedInCredentialsError,
    LinkedInResponseError,
    LinkedInTimeoutError,
)
from app.core.dependencies import get_authenticated_linkedin_client
from app.main import create_app
from app.parsers.linkedin_jobs import HTMLStructureError


class FakeAuthenticatedLinkedInClient:
    """Fake client with a static results page."""

    async def search_jobs(self, keywords: str, geo_id: str, f_tpr: str, start: int) -> str:
        """Returns a card and an accessible next-page control."""

        assert (keywords, geo_id, f_tpr, start) == (
            "biomedicina",
            "90009574",
            "r2592000",
            0,
        )
        return """
        <div componentkey="job-card-component-ref-123">
          <p><span aria-hidden="true">Analista de biomedicina</span></p>
          <p>Empresa</p><p>São Paulo, Brasil</p>
        </div>
        <a rel="next" href="?start=1">Próxima</a>
        """


def test_search_jobs_response_contract() -> None:
    """Returns the query, pagination, and jobs without exposing HTML."""

    fake_client = FakeAuthenticatedLinkedInClient()
    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: fake_client

    with TestClient(app) as client:
        response = client.get("/api/jobs/search", params={"keywords": "biomedicina"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == {
        "keywords": "biomedicina",
        "geo_id": "90009574",
        "f_tpr": "r2592000",
    }
    assert body["pagination"] == {
        "start": 0,
        "count": 1,
        "next_start": 1,
        "has_next": True,
    }
    assert body["jobs"][0]["id"] == "123"
    assert "html" not in body


@pytest.mark.parametrize("f_tpr", ["r86400", "r604800"])
def test_search_jobs_accepts_linkedin_location_and_time_filter(f_tpr: str) -> None:
    """Passes the requested location and supported time range through the API."""

    class FilteredClient:
        async def search_jobs(
            self,
            keywords: str,
            geo_id: str,
            f_tpr: str,
            start: int,
        ) -> str:
            assert (keywords, geo_id, f_tpr, start) == (
                "software engineer",
                "90009574",
                f_tpr,
                25,
            )
            return """
            <div componentkey="job-card-component-ref-456">
              <p><span aria-hidden="true">Software Engineer</span></p>
              <p>Empresa</p><p>São Paulo, Brasil</p>
            </div>
            """

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: FilteredClient()

    with TestClient(app) as client:
        response = client.get(
            "/api/jobs/search",
            params={
                "keywords": "software engineer",
                "geo_id": "90009574",
                "f_TPR": f_tpr,
                "start": 25,
            },
        )

    assert response.status_code == 200
    assert response.json()["query"] == {
        "keywords": "software engineer",
        "geo_id": "90009574",
        "f_tpr": f_tpr,
    }


def test_search_jobs_rejects_unsupported_time_filter() -> None:
    """Accepts only LinkedIn's supported 24-hour, week, and month filters."""

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: (
        FakeAuthenticatedLinkedInClient()
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/jobs/search",
            params={"keywords": "biomedicina", "f_TPR": "r3600"},
        )

    assert response.status_code == 422


def test_search_jobs_rejects_negative_start() -> None:
    """Validates that the pagination offset is non-negative."""

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: (
        FakeAuthenticatedLinkedInClient()
    )

    with TestClient(app) as client:
        response = client.get("/api/jobs/search", params={"keywords": "biomedicina", "start": -1})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("upstream_error", "expected_status"),
    [
        (LinkedInCredentialsError("missing credentials"), 503),
        (LinkedInAuthenticationError("unauthorized"), 502),
        (LinkedInTimeoutError("timed out"), 504),
        (LinkedInResponseError("invalid response"), 502),
        (HTMLStructureError("unexpected HTML"), 502),
    ],
)
def test_search_jobs_maps_upstream_errors(
    upstream_error: Exception,
    expected_status: int,
) -> None:
    """Converts integration and parser errors into the documented HTTP statuses."""

    class FailingClient:
        async def search_jobs(self, keywords: str, geo_id: str, f_tpr: str, start: int) -> str:
            raise upstream_error

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: FailingClient()

    with TestClient(app) as client:
        response = client.get("/api/jobs/search", params={"keywords": "biomedicina"})

    assert response.status_code == expected_status
