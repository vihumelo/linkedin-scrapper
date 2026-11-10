"""Offline tests for the job details HTTP endpoint."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_job_cache, get_public_linkedin_client
from app.main import create_app
from app.schemas.jobs import JobDetail

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "linkedin_job_detail.html"


class FakePublicLinkedInClient:
    """Fake client that returns the real HTML preserved for testing."""

    async def get_job_details_html(self, job_id: str) -> str:
        """Returns the reference HTML without making an external request."""

        return FIXTURE_PATH.read_text(encoding="utf-8")


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
    """Returns validated details without including the raw HTML page."""

    app = create_app()
    app.dependency_overrides[get_public_linkedin_client] = lambda: FakePublicLinkedInClient()
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get("/api/jobs/4486249045")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "linkedin_jobs_guest"
    assert payload["job"]["id"] == "4486249045"
    assert payload["job"]["title"] == "Técnico em Engenharia Clinica"
    assert payload["job"]["url"] == "https://www.linkedin.com/jobs/view/4486249045/"
    assert "description_html" in payload["job"]
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
    app.dependency_overrides[get_public_linkedin_client] = lambda: FakePublicLinkedInClient()
    app.dependency_overrides[get_job_cache] = lambda: cache

    with TestClient(app) as client:
        response = client.get("/api/jobs/4486249045?refresh=true")

    assert response.status_code == 200
    assert response.json()["job"]["title"] == "Técnico em Engenharia Clinica"
    assert cache.get_calls == []
    assert cache.saved_jobs[0].title == "Técnico em Engenharia Clinica"


def test_get_job_details_rejects_non_numeric_id() -> None:
    """Returns 422 when the job ID contains anything other than digits."""

    app = create_app()
    app.dependency_overrides[get_public_linkedin_client] = lambda: FakePublicLinkedInClient()
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get("/api/jobs/not-a-job-id")

    assert response.status_code == 422


@pytest.mark.parametrize("job_id", ["١٢٣", "１２３"])
def test_get_job_details_rejects_unicode_decimal_id(job_id: str) -> None:
    """Rejects Unicode digits because LinkedIn IDs use ASCII digits."""

    app = create_app()
    app.dependency_overrides[get_public_linkedin_client] = lambda: FakePublicLinkedInClient()
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 422
