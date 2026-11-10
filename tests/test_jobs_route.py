"""Tests for the job search HTTP endpoint."""

from fastapi.testclient import TestClient

from app.core.dependencies import get_authenticated_linkedin_client
from app.main import create_app


class FakeAuthenticatedLinkedInClient:
    """Fake client with a static results page."""

    async def search_jobs(self, keywords: str, geo_id: str, start: int) -> str:
        """Returns a card and an accessible next-page control."""

        assert (keywords, geo_id, start) == ("biomedicina", "106057199", 0)
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
    assert body["query"] == {"keywords": "biomedicina", "geo_id": "106057199"}
    assert body["pagination"] == {
        "start": 0,
        "count": 1,
        "next_start": 1,
        "has_next": True,
    }
    assert body["jobs"][0]["id"] == "123"
    assert "html" not in body


def test_search_jobs_rejects_negative_start() -> None:
    """Validates that the pagination offset is non-negative."""

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: (
        FakeAuthenticatedLinkedInClient()
    )

    with TestClient(app) as client:
        response = client.get("/api/jobs/search", params={"keywords": "biomedicina", "start": -1})

    assert response.status_code == 422
