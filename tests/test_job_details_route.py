"""Offline tests for the job details HTTP endpoint."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.clients.authenticated_client import (
    LinkedInAuthenticationError,
    LinkedInCredentialsError,
    LinkedInJobNotFoundError,
    LinkedInResponseError,
    LinkedInServiceUnavailableError,
    LinkedInTimeoutError,
)
from app.core.dependencies import get_authenticated_linkedin_client, get_job_cache
from app.main import create_app
from app.parsers.linkedin_voyager_job_details import JobDetailVoyagerStructureError
from app.schemas.jobs import JobDetail

JOB_ID = "4486249045"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "linkedin_job_detail_voyager.json"


class FakeAuthenticatedLinkedInClient:
    """Fake client that returns a Voyager payload without making a network request."""

    async def get_job_details(self, job_id: str) -> dict[str, object]:
        """Returns the complete sanitized real Voyager response fixture."""

        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class FakeJobCache:
    """Empty fake cache that keeps route tests offline."""

    def __init__(self, cached_job: JobDetail | None = None) -> None:
        """Configures the record returned by the cache and prepares its history."""

        self.cached_job = cached_job
        self.get_calls: list[str] = []
        self.saved_jobs: list[JobDetail] = []

    async def get(self, job_id: str) -> JobDetail | None:
        """Simulates a cache miss for the job."""

        self.get_calls.append(job_id)
        return self.cached_job

    async def save(self, job: JobDetail) -> None:
        """Accepts the write without persisting test data."""

        self.saved_jobs.append(job)

    async def delete(self, job_id: str) -> None:
        """Implements the operation required by the cache contract."""

        if self.cached_job and self.cached_job.id == job_id:
            self.cached_job = None


def test_get_job_details_returns_structured_json() -> None:
    """Returns validated details parsed from a Voyager JSON payload."""

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: (
        FakeAuthenticatedLinkedInClient()
    )
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get("/api/job/4486249045")

    assert response.status_code == 200
    payload = response.json()
    assert "source" not in payload
    assert payload["job"]["id"] == JOB_ID
    assert payload["job"]["title"] == "Técnico em Engenharia Clinica"
    assert payload["job"]["company"] == "[EMPRESA REDIGIDA]"
    assert payload["job"]["industry"] == "Hospitals and Health Care"
    assert payload["job"]["workplace_type"] == "On-site"
    assert payload["job"]["url"] == f"https://www.linkedin.com/jobs/view/{JOB_ID}/"
    assert payload["job"]["posted"] == datetime.fromtimestamp(1793968839, UTC).isoformat()
    assert "description_html" not in payload["job"]
    assert "<html" not in response.text


def test_refresh_query_bypasses_cached_job() -> None:
    """The refresh=true query parameter forces a LinkedIn request and updates the cache."""

    cache = FakeJobCache(
        JobDetail(
            id="4486249045",
            title="Título antigo",
            company="Empresa antiga",
            location="São Paulo, Brasil",
            url="https://www.linkedin.com/jobs/view/4486249045/",
            description_text="Descrição antiga.",
        )
    )
    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: (
        FakeAuthenticatedLinkedInClient()
    )
    app.dependency_overrides[get_job_cache] = lambda: cache

    with TestClient(app) as client:
        response = client.get("/api/job/4486249045?refresh=true")

    assert response.status_code == 200
    assert response.json()["job"]["title"] == "Técnico em Engenharia Clinica"
    assert cache.get_calls == []
    assert cache.saved_jobs[0].title == "Técnico em Engenharia Clinica"


def test_get_job_details_rejects_non_numeric_id() -> None:
    """Returns 422 when the job ID contains anything other than digits."""

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: (
        FakeAuthenticatedLinkedInClient()
    )
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get("/api/job/not-a-job-id")

    assert response.status_code == 422


@pytest.mark.parametrize("job_id", ["١٢٣", "１２３"])
def test_get_job_details_rejects_unicode_decimal_id(job_id: str) -> None:
    """Rejects Unicode digits because LinkedIn IDs use ASCII digits."""

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: (
        FakeAuthenticatedLinkedInClient()
    )
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get(f"/api/job/{job_id}")

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("upstream_error", "expected_status"),
    [
        (LinkedInJobNotFoundError("not found"), 404),
        (LinkedInCredentialsError("missing credentials"), 503),
        (LinkedInServiceUnavailableError("unavailable"), 503),
        (LinkedInTimeoutError("timed out"), 504),
        (LinkedInAuthenticationError("unauthorized"), 502),
        (LinkedInResponseError("invalid response"), 502),
        (JobDetailVoyagerStructureError("invalid structure"), 502),
    ],
)
def test_get_job_details_maps_upstream_errors(
    upstream_error: Exception,
    expected_status: int,
) -> None:
    """Converts integration and parser errors into the documented HTTP statuses."""

    class FailingClient:
        async def get_job_details(self, job_id: str) -> dict[str, object]:
            raise upstream_error

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: FailingClient()
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get(f"/api/job/{JOB_ID}")

    assert response.status_code == expected_status
